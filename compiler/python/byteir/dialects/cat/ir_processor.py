from byteir import ir
from byteir.passmanager import PassManager

from pathlib import Path
import os
import time
import multiprocessing
import torch

BYTEIR_CAT_ATTR = "__byteir_cat_fusion__"

available_cuda_device_num = torch.cuda.device_count()
MAX_COMPILATION_PARALLELISM = available_cuda_device_num

def func_hash_str(func):
    hash_str = ""
    ops = func.entry_block.operations
    for op in ops:
        op_name = op.operation.name
        # op name
        hash_str += op_name
        # args
        hash_str += "("
        for operand in op.operands:
            hash_str += f"{operand.type},"
        hash_str += ")"
    return hash_str

class IRProcessor:
    def __init__(self, job_name, workdir, compile_parallelism = MAX_COMPILATION_PARALLELISM):
        self.job_name = job_name
        self.workdir = workdir
        self.module = None
        self.enable_ait_reuse = True
        self.ait_reuse_dict = {} # key: hash key, value: Tuple(dll_name, ait_module_path)
        self.compile_parallelism = min(compile_parallelism, MAX_COMPILATION_PARALLELISM)
        self.pool = multiprocessing.Pool(compile_parallelism)

    def _get_builder(self, module, subgraph_name, backend="ait"):
        assert module != None
        if backend == "ait":
            from byteir.dialects.cat.ir_translator.ait_builder import ait_builder
            return ait_builder(module, workdir=self.workdir, subgraph_name=subgraph_name)
        else:
            raise RuntimeError(f"Unsupported runtime backend {backend}")

    def load_from_file(self, module_file):
        self.module = ir.Module.parse(Path(module_file).read_text())

    def _dump_ir(self, ir_name):
        ir_file = f'{self.workdir}/{ir_name}'
        with open(ir_file, "w") as f:
            f.write(self.module.operation.get_asm())

    def preprocess_pass(self, dump_ir=False):
        with self.module.context:
            pass_arg = "builtin.module(cat-preprocess)"
            pm = PassManager.parse(pass_arg)
            pm.run(self.module.operation)
            if dump_ir:
                self._dump_ir("{}.mhlo.simplified.mlir".format(self.job_name))
        return self.module

    def hlo_opt_pass(self, outline_single_elemwise_op=False, dump_ir=False, aggressive_mode=False):
        with self.module.context:
            if outline_single_elemwise_op:
                if aggressive_mode:
                    pass_arg = "builtin.module(hlo-opt{outline-single-elemwise-op outline-cat-op aggressive-cat-fusion})"
                else:
                    pass_arg = "builtin.module(hlo-opt{outline-single-elemwise-op outline-cat-op})"
            else:
                pass_arg = "builtin.module(hlo-opt{outline-cat-op})"
            pm = PassManager.parse(pass_arg)
            pm.run(self.module.operation)
            if dump_ir:
                self._dump_ir("{}.hlo_opt.mlir".format(self.job_name))
        return self.module

    def cat_opt_pass(self, anchor_only=False, dump_ir=False, aggressive_mode=False):
        with self.module.context:
            if anchor_only:
                pass_arg = "builtin.module(cat-opt{anchor-only})"
            else:
                if aggressive_mode:
                    pass_arg = "builtin.module(cat-opt{aggressive-mode})"
                else:
                    pass_arg = "builtin.module(cat-opt)"
            pm = PassManager.parse(pass_arg)
            pm.run(self.module.operation)
            if dump_ir:
                self._dump_ir("{}.cat_opt.mlir".format(self.job_name))
        return self.module

    def ait_opt_pass(self, anchor_only=False, dump_ir=False):
        if not anchor_only:
            builder = self._get_builder()
            builder.compile()
            return self.module
        funcNameArg = ""
        aitLibPathArg = ""
        dllPaths = []
        
        func_ir_str_list = []
        for func in self.module.body.operations:
            if BYTEIR_CAT_ATTR not in func.attributes:
                continue
            func_ir_str = func.get_asm(large_elements_limit=None)
            if self.enable_ait_reuse:
                hash_str = func_hash_str(func)
                hash_key = hash(hash_str)
                if hash_key in self.ait_reuse_dict:
                    funcNameArg += func.name.value + ","
                    aitLibPathArg += self.ait_reuse_dict[hash_key][0] + ","
                    dllPaths.append(self.ait_reuse_dict[hash_key][1])
                else:
                    builder = self._get_builder(module=func, subgraph_name=func.name.value, backend="ait")
                    # builder.benchmark()
                    funcNameArg += func.name.value + ","
                    aitLibPathArg += builder.dll_name + ","
                    dllPaths.append(builder.ait_module_path)
                    self.ait_reuse_dict[hash_key] = (builder.dll_name, builder.ait_module_path)
                    func_ir_str_list.append(func_ir_str)
            else:
                builder = self._get_builder(module=func, subgraph_name=func.name.value, backend="ait")
                # builder.benchmark()
                funcNameArg += func.name.value + ","
                aitLibPathArg += builder.dll_name + ","
                dllPaths.append(builder.ait_module_path)
                func_ir_str_list.append(func_ir_str)
        
        # compile and benchmark
        print("compile ait module using {} processes".format(min(len(func_ir_str_list), self.compile_parallelism)))
        t_st = time.time()
        for func_ir_str in func_ir_str_list:
            self.pool.apply_async(_parallel_ait_compile, (self.workdir, func_ir_str))
            # _parallel_ait_compile(self.workdir, func_ir_str)
        
        self.pool.close()
        self.pool.join()
        t_ed = time.time()
        print("compilation finished in {}s".format(t_ed-t_st))

        with self.module.context:
            pm = PassManager.parse("builtin.module(func.func(gen-ait-config{{func-names={} ait-lib-paths={}}}))".format(funcNameArg, aitLibPathArg))
            pm.run(self.module.operation)
            if dump_ir:
                self._dump_ir("{}.ait_opt.mlir".format(self.job_name))
        
        return self.module, dllPaths

    def bufferize_opt_pass(self, dump_ir=False):
        with self.module.context:
            pass_arg = "builtin.module(byteir-bufferize-opt)"
            pm = PassManager.parse(pass_arg)
            pm.run(self.module.operation)
            if dump_ir:
                self._dump_ir("{}.bufferize_opt.mlir".format(self.job_name))
        return self.module

    def execute(self, inputs, backend="ait"):
        module = self.module.body.operations[0]
        subgraph_name = module.name.value
        builder = self._get_builder(module=module, subgraph_name=subgraph_name, backend=backend)
        builder.compile()
        return builder.execute(inputs)

    def benchmark(self, backend="ait", num_trials=5):
        module = self.module.body.operations[0]
        subgraph_name = module.name.value
        builder = self._get_builder(module=module, subgraph_name=subgraph_name, backend=backend)
        builder.compile()
        builder.benchmark(num_trials)

    def profile(self, backend="ait"):
        pass


def _parallel_ait_compile(workdir: str, ir_str: str):
    os.environ["CUDA_VISIBLE_DEVICES"]=str(os.getpid() % available_cuda_device_num)
    context = ir.Context()
    module = ir.Module.parse(ir_str, context)
    assert len(module.body.operations) == 1
    func = module.body.operations[0]
    from byteir.dialects.cat.ir_translator.ait_builder import ait_builder
    builder = ait_builder(func, workdir=workdir, subgraph_name=func.name.value)
    builder.compile()
    builder.benchmark()

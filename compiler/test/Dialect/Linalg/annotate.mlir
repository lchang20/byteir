// RUN: byteir-opt %s -linalg-bufferize --transform-dialect-interpreter -cse -canonicalize | FileCheck %s

transform.sequence failures(propagate) {
^bb0(%arg1: !pdl.operation):
  %0 = transform.structured.match ops{["linalg.matmul"]} in %arg1 : (!pdl.operation) -> !pdl.operation
  %1, %loops:3 = transform.structured.tile %0 [128, 128, 32] {interchange = [0, 1, 2]} : (!pdl.operation) -> (!pdl.operation, !pdl.operation, !pdl.operation, !pdl.operation)
  transform.annotate %loops#0 { __byteir_loop_to_simt__ = "block_id.y" }
  transform.annotate %loops#1 { __byteir_loop_to_simt__ = "block_id.x" }
  transform.annotate %1 { __scope__ = "threadblock" }
  transform.annotate %1 { __target__ = "nv_sm_80" }
  %2 = transform.structured.match ops{["func.func"]} in %arg1 : (!pdl.operation) -> !pdl.operation
  transform.annotate %2 {__byteir_to_gpu__, __byteir_copy_async__, __byteir_block_size__ = [32, 2, 2]}
}

#map = affine_map<(d0, d1) -> (d1 * 2048 + d0)>

// CHECK-LABEL: func.func @hgemm
func.func @hgemm(%arg0: memref<5376x2048xf16>, %arg1: memref<2048x5376xf16, #map>, %arg2: memref<5376x5376xf16>) {
  // CHECK: linalg.matmul {__scope__ = "threadblock", __target__ = "nv_sm_80"}
  linalg.matmul ins(%arg0, %arg1: memref<5376x2048xf16>, memref<2048x5376xf16, #map>)
                     outs(%arg2: memref<5376x5376xf16>)
  // CHECK: {__byteir_loop_to_simt__ = "block_id.x"}
  // CHECK: {__byteir_loop_to_simt__ = "block_id.y"}
  return
}
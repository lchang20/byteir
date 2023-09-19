// Copyright (c) 2023, Tri Dao.

// Splitting the different head dimensions to different files to speed up
// compilation.

#include "flash_bwd_launch_template.h"
namespace brt {
namespace cuda {
namespace kernel {
template <>
void run_mha_bwd_<cutlass::bfloat16_t, 224>(Flash_bwd_params &params,
                                            cudaStream_t stream,
                                            const bool configure) {
  run_mha_bwd_hdim224<cutlass::bfloat16_t>(params, stream, configure);
}
} // namespace kernel
} // namespace cuda
} // namespace brt
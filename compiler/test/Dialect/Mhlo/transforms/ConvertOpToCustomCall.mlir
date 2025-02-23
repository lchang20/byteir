// RUN: byteir-opt %s -convert-op-to-customcall | FileCheck %s

func.func @convert_rng_static() -> tensor<8x1024x768xf32> attributes {__placeholder__byre.entry_point} {
  %16 = mhlo.constant dense<1.000000e+00> : tensor<f32>
  %17 = mhlo.constant dense<0.000000e+00> : tensor<f32>
  %18 = mhlo.constant dense<[8, 1024, 768]> : tensor<3xi64>
  %26 = "mhlo.rng"(%17, %16, %18) {rng_distribution = #mhlo.rng_distribution<UNIFORM>} : (tensor<f32>, tensor<f32>, tensor<3xi64>) -> tensor<8x1024x768xf32>
  return %26 : tensor<8x1024x768xf32>
}
// CHECK-LABEL: func.func @convert_rng_static
// CHECK-NEXT:  mhlo.constant
// CHECK-NEXT:  mhlo.constant
// CHECK-NEXT:  byre.compute @GetSeed
// CHECK-NEXT:  byre.compute @GetOffset
// CHECK-NEXT:  mhlo.custom_call
// CHEKC-SAME:  call_target_name = "byteir.rng_uniform"

func.func @convert_rng_dynamic(%arg0: tensor<?x?x?xf32>) -> tensor<?x?x?xf32> attributes {__placeholder__byre.entry_point} {
  %16 = mhlo.constant dense<1.000000e+00> : tensor<f32>
  %17 = mhlo.constant dense<0.000000e+00> : tensor<f32>
  %shape = shape.shape_of %arg0 : tensor<?x?x?xf32> -> tensor<3xindex>
  %shape1 = arith.index_cast %shape : tensor<3xindex> to tensor<3xi64>
  %26 = "mhlo.rng"(%17, %16, %shape1) {rng_distribution = #mhlo.rng_distribution<UNIFORM>} : (tensor<f32>, tensor<f32>, tensor<3xi64>) -> tensor<?x?x?xf32>
  return %26 : tensor<?x?x?xf32>
}
// CHECK-LABEL: func.func @convert_rng_dynamic
// CHECK-NEXT:  mhlo.constant
// CHECK-NEXT:  mhlo.constant
// CHECK-NEXT:  shape.shape_of
// CHECK-NEXT:  arith.index_cast
// CHECK-NEXT:  byre.compute @GetSeed
// CHECK-NEXT:  byre.compute @GetOffset
// CHECK-NEXT:  mhlo.custom_call
// CHEKC-SAME:  call_target_name = "byteir.rng_uniform"
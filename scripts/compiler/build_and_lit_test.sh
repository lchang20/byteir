#!/bin/bash

set -e
set -x

# path to script
CUR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# path to byteir root
ROOT_PROJ_DIR="$CUR_DIR/../.."
# path to byteir/compiler
PROJ_DIR="$ROOT_PROJ_DIR/compiler"
# dir to build
BUILD_DIR="$PROJ_DIR/build"
# dir to install
INSTALL_DIR="$BUILD_DIR/byre_install"

source $CUR_DIR/../prepare.sh

LLVM_INSTALL_DIR="$1"
prepare_for_compiler

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cmake "-H$PROJ_DIR/cmake" \
      "-B$BUILD_DIR" \
      -GNinja \
      -DCMAKE_BUILD_TYPE=Release \
      -DLLVM_INSTALL_PATH="$LLVM_INSTALL_DIR" \
      -DLLVM_EXTERNAL_LIT=$(which lit) \
      -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
      -DBYTEIR_ENABLE_BINDINGS_PYTHON=ON

cmake --build "$BUILD_DIR" --config Release --target all check-byteir install
cmake --build "$BUILD_DIR" --target check-byteir-numerical
cmake --build "$BUILD_DIR" --target byteir-python-pack

# TODO: make this test more robust
# test byteir.compile
pushd $ROOT_PROJ_DIR
PYTHONPATH=./compiler/build/python_packages/byteir python3 -m byteir.tools.compiler ./compiler/test/E2E/MLPInference/input.mlir -o ./test.mlir --entry_func forward
rm -f ./test.mlir
rm -f ./test.mlir.ptx
popd

//===- cpu_work_queue.h ---------------------------------------*--- C++ -*-===//
//
// Copyright 2022 ByteDance Ltd. and/or its affiliates. All rights reserved.
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
//===----------------------------------------------------------------------===//

#pragma once

#include "brt/core/context/work_queue.h"
#include <functional>
#include <vector>

namespace brt {
namespace cpu {

// WorkQueue which alawys runs host task inplace
class CPUNaiveWorkQueue : public WorkQueue {
public:
  explicit CPUNaiveWorkQueue(const std::string &name = "cpu_naive");

  common::Status AddTask(int /*task_type*/, const void * /*func*/,
                         void ** /*args*/) override;

  common::Status Sync() override;

  common::Status AddHostTask(std::function<void(void)> &&task) override;
};

// WorkQueue which runs host task lazily
class CPULazyWorkQueue : public WorkQueue {
public:
  explicit CPULazyWorkQueue(const std::string &name = "cpu_lazy");

  common::Status AddTask(int /*task_type*/, const void * /*func*/,
                         void ** /*args*/) override;

  common::Status Sync() override;

  common::Status AddHostTask(std::function<void(void)> &&task) override;

private:
  std::vector<std::function<void(void)>> tasks;
};
} // namespace cpu
} // namespace brt

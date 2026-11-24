# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Conftest for reviewer replay regression tests.

Provides the --live CLI flag. Without it, every test marked `live_llm`
is skipped — replays call the LLM via SDK which is slow and costs API
tokens, so CI / regular `pytest` runs should not trigger them.

Usage:
  pytest tests/regression/reviewer                        # auto-skip (default)
  pytest tests/regression/reviewer --live                 # actually call the reviewer LLM
  pytest tests/regression/reviewer --live -k let_exit     # single fixture
"""
# --live is registered at tests/conftest.py so collection is consistent even
# when this directory is not part of the selected test path.

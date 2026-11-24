# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Tests for session naming system."""

from workflow_controller.api.session_api import _is_design_md_compliant_name


class TestDesignMdCompliantName:
    """Test _is_design_md_compliant_name regex."""

    @staticmethod
    def test_handoff_name_matches():
        """Handoff names should match."""
        assert _is_design_md_compliant_name("76c3c040-handoff-4") is True
        assert _is_design_md_compliant_name("abc123-handoff-1") is True
        assert _is_design_md_compliant_name("00000000-handoff-999") is True

    @staticmethod
    def test_continuation_name_matches():
        """Continuation names should match."""
        assert _is_design_md_compliant_name("76c3c040-continue-2") is True
        assert _is_design_md_compliant_name("abc123-continue-1") is True
        assert _is_design_md_compliant_name("00000000-continue-999") is True

    @staticmethod
    def test_non_compliant_names_rejected():
        """Non-compliant names should not match."""
        assert _is_design_md_compliant_name("session 07-09 20:30") is False
        assert _is_design_md_compliant_name("ops-registry-invoke") is False
        assert _is_design_md_compliant_name("开发支持float16的xlogy算子") is False
        assert _is_design_md_compliant_name("按既定计划推进任务") is False
        assert _is_design_md_compliant_name("") is False

    @staticmethod
    def test_old_format_with_operator_rejected():
        """Old format with operator prefix should not match."""
        assert _is_design_md_compliant_name("xlogy-76c3c040-handoff-1") is False
        assert _is_design_md_compliant_name("operator-abc123-continue-2") is False

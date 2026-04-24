from __future__ import annotations

import sys
import traceback
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class TestEvidenceRow:
    test_name: str
    actual_result: str
    pass_or_fail: str


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.evidence_rows: list[TestEvidenceRow] = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.evidence_rows.append(
            TestEvidenceRow(
                test_name=self.getDescription(test),
                actual_result="Completed without assertion or runtime error.",
                pass_or_fail="PASS",
            )
        )

    def addFailure(self, test, err):
        super().addFailure(test, err)
        msg = self._compact_error(err)
        self.evidence_rows.append(
            TestEvidenceRow(
                test_name=self.getDescription(test),
                actual_result=msg,
                pass_or_fail="FAIL",
            )
        )

    def addError(self, test, err):
        super().addError(test, err)
        msg = self._compact_error(err)
        self.evidence_rows.append(
            TestEvidenceRow(
                test_name=self.getDescription(test),
                actual_result=msg,
                pass_or_fail="FAIL",
            )
        )

    @staticmethod
    def _compact_error(err) -> str:
        exc_type, exc_value, exc_tb = err
        formatted = traceback.format_exception_only(exc_type, exc_value)
        message = "".join(formatted).strip()
        if message:
            return message
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).strip()
        return tb_text.splitlines()[-1] if tb_text else "Unknown failure."


class EvidenceRunner(unittest.TextTestRunner):
    resultclass = EvidenceResult


def main() -> int:
    suite = unittest.defaultTestLoader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py")
    runner = EvidenceRunner(verbosity=2)
    result: EvidenceResult = runner.run(suite)  # type: ignore[assignment]

    print("\nEvidence Summary")
    print("===============")
    for row in result.evidence_rows:
        print(f"Test Name: {row.test_name}")
        print(f"Actual Result: {row.actual_result}")
        print(f"Pass or Fail: {row.pass_or_fail}")
        print("")

    print(
        f"Totals -> Ran: {result.testsRun}, "
        f"Passed: {len(result.evidence_rows) - len(result.failures) - len(result.errors)}, "
        f"Failed: {len(result.failures) + len(result.errors)}"
    )

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

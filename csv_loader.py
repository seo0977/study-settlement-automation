"""
csv_loader.py
-------------
주간 정산 CSV 파일을 읽어 settlement.py에서 바로 쓸 수 있는
MemberWeekInput 리스트로 변환합니다.

CSV 포맷 (헤더 포함, UTF-8):
    name,study_hours,merit_points
    Member1,61.05,2
    Member2,50.07,-0.5

기존에는 process_week() 호출부에 MemberWeekInput을 하나하나
하드코딩했는데, 실제 운영에서는 매주 스터디원 수가 바뀌고
데이터도 엑셀/구글시트에서 CSV로 내보내는 경우가 많아
이 변환 단계를 분리했습니다.
"""

import csv
from pathlib import Path
from settlement import MemberWeekInput


class CSVFormatError(Exception):
    """CSV 필드 누락, 타입 오류 등 포맷 문제를 알리는 예외"""
    pass


REQUIRED_COLUMNS = {"name", "study_hours", "merit_points"}


def load_week_entries(csv_path: str | Path) -> list[MemberWeekInput]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")

    entries = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise CSVFormatError(
                f"필수 컬럼이 없습니다: {', '.join(missing)} "
                f"(필요한 컬럼: {', '.join(sorted(REQUIRED_COLUMNS))})"
            )

        for row_num, row in enumerate(reader, start=2):  # 헤더가 1행
            name = row["name"].strip()
            if not name:
                raise CSVFormatError(f"{row_num}행: name이 비어 있습니다.")

            try:
                study_hours = float(row["study_hours"])
            except ValueError:
                raise CSVFormatError(
                    f"{row_num}행({name}): study_hours 값이 숫자가 아닙니다 "
                    f"('{row['study_hours']}')"
                )

            merit_raw = row.get("merit_points", "").strip()
            try:
                merit_points = float(merit_raw) if merit_raw else 0
            except ValueError:
                raise CSVFormatError(
                    f"{row_num}행({name}): merit_points 값이 숫자가 아닙니다 "
                    f"('{merit_raw}')"
                )

            entries.append(MemberWeekInput(
                name=name, study_hours=study_hours, merit_points=merit_points
            ))

    if not entries:
        raise CSVFormatError("CSV에 데이터 행이 없습니다.")

    return entries


if __name__ == "__main__":
    import sys
    from settlement import SettlementLedger

    if len(sys.argv) < 3:
        print("사용법: python csv_loader.py <week_label> <threshold_hours> <csv_path>")
        print("예시:   python csv_loader.py 'Week 3' 55 data/week3.csv")
        sys.exit(1)

    week_label, threshold_hours, csv_path = sys.argv[1], float(sys.argv[2]), sys.argv[3]

    entries = load_week_entries(csv_path)
    ledger = SettlementLedger()
    ledger.process_week(week_label, threshold_hours, entries)
    print(ledger.week_report(week_label))

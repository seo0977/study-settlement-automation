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

이 모듈은 CSV의 "형식"만 검증합니다 (컬럼 존재 여부, 숫자 형식,
빈 값). "값이 도메인상 타당한가"(음수 시간 등)와 "이 이름이
등록된 멤버인가"는 settlement.py의 SettlementLedger가 검증합니다.
책임을 이렇게 나눈 이유는, 형식 오류와 도메인 규칙 위반을
같은 계층에서 섞으면 어느 쪽 문제인지 파악하기 어려워지기 때문입니다.
"""

import csv
from pathlib import Path
from settlement import MemberWeekInput


class CSVFormatError(Exception):
    """CSV 필드 누락, 타입 오류, 중복 행 등 포맷 문제를 알리는 예외"""
    pass


REQUIRED_COLUMNS = {"name", "study_hours", "merit_points"}

# 명백히 잘못된 입력(오타, 단위 실수 등)을 조기에 잡기 위한 형식적 상한선.
# 실제 운영 규칙(자격 판정 기준 등)과는 별개로, "이 값이 물리적으로 말이 되는가"만 확인합니다.
MAX_PLAUSIBLE_HOURS = 168  # 한 주 최대 시간(24*7)을 넘는 값은 명백한 오타로 간주
MAX_PLAUSIBLE_MERIT = 100  # 상벌점이 이 범위를 넘으면 오타 가능성이 높다고 간주


def load_week_entries(csv_path: str | Path) -> list[MemberWeekInput]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")

    entries = []
    seen_names = set()

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

            # 중복 멤버 검증: 엑셀 복붙 실수 등으로 같은 사람이 두 번 들어오면
            # process_week()에서 같은 사람이 두 번 처리되어 정산이 조용히 틀어질 수 있음
            if name in seen_names:
                raise CSVFormatError(
                    f"{row_num}행: '{name}'이(가) 이 CSV에 중복으로 등장합니다. "
                    f"엑셀/시트에서 복붙 실수가 없었는지 확인하세요."
                )
            seen_names.add(name)

            try:
                study_hours = float(row["study_hours"])
            except ValueError:
                raise CSVFormatError(
                    f"{row_num}행({name}): study_hours 값이 숫자가 아닙니다 "
                    f"('{row['study_hours']}')"
                )
            if not (0 <= study_hours <= MAX_PLAUSIBLE_HOURS):
                raise CSVFormatError(
                    f"{row_num}행({name}): study_hours 값이 비정상적입니다 "
                    f"({study_hours}h). 0~{MAX_PLAUSIBLE_HOURS}시간 범위를 벗어났습니다. "
                    f"입력 오타를 확인하세요."
                )

            merit_raw = row.get("merit_points", "").strip()
            try:
                merit_points = float(merit_raw) if merit_raw else 0
            except ValueError:
                raise CSVFormatError(
                    f"{row_num}행({name}): merit_points 값이 숫자가 아닙니다 "
                    f"('{merit_raw}')"
                )
            if abs(merit_points) > MAX_PLAUSIBLE_MERIT:
                raise CSVFormatError(
                    f"{row_num}행({name}): merit_points 값이 비정상적으로 큽니다 "
                    f"({merit_points}). 입력 오타를 확인하세요."
                )

            entries.append(MemberWeekInput(
                name=name, study_hours=study_hours, merit_points=merit_points
            ))

    if not entries:
        raise CSVFormatError("CSV에 데이터 행이 없습니다.")

    return entries


def _parse_cli_args(argv: list[str]) -> tuple[str, float, str]:
    """CLI 인자를 파싱하고, 잘못된 입력이면 사용법과 함께 알기 쉬운 에러를 던집니다."""
    if len(argv) < 4:
        raise CSVFormatError(
            "사용법: python csv_loader.py <week_label> <threshold_hours> <csv_path>\n"
            "예시:   python csv_loader.py 'Week 3' 55 data/week3.csv"
        )
    week_label, threshold_raw, csv_path = argv[1], argv[2], argv[3]
    try:
        threshold_hours = float(threshold_raw)
    except ValueError:
        raise CSVFormatError(
            f"threshold_hours는 숫자여야 합니다 (입력값: '{threshold_raw}')"
        )
    return week_label, threshold_hours, csv_path


if __name__ == "__main__":
    import sys
    from settlement import SettlementLedger

    try:
        week_label, threshold_hours, csv_path = _parse_cli_args(sys.argv)
        entries = load_week_entries(csv_path)

        ledger = SettlementLedger()
        # CSV에 등장한 멤버를 이번 실행에서만 등록 (실제 운영에서는 스터디원 명단을
        # 미리 한 번 register_member()로 등록해두고, 매주 process_week만 호출하는 것을 권장)
        for e in entries:
            if e.name not in ledger.members:
                ledger.register_member(e.name)

        ledger.process_week(week_label, threshold_hours, entries)
        print(ledger.week_report(week_label))

    except (CSVFormatError, FileNotFoundError, ValueError) as e:
        print(f"오류: {e}")
        sys.exit(1)

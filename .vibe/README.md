# vibe-kit (repo-local)

이 폴더는 “에이전트/유저가 프로젝트를 잃지 않게” 도와주는 로컬 도구함입니다.

## 하는 일 (요약)
- 레포를 로컬로 스캔해서 컨텍스트 DB를 만들고(`.vibe/db/context.sqlite`), 요약/리포트를 생성합니다.
- 에이전트에게 붙여 넣을 수 있는 요약 문서를 `.vibe/context/` 아래에 생성합니다.
- 기본적으로 네트워크/API 호출을 하지 않습니다(로컬 파일 기반).

## 빠른 시작
- (권장) 레포 자동 설정(한 번): `python3 scripts/vibe.py configure --apply`
- 한 방 진단(권장): `python3 scripts/vibe.py doctor --full`
- (Windows) `scripts\\vibe.cmd doctor --full`
- 감시(선택): `python3 scripts/vibe.py watch`

## 주요 명령
- 레포 자동 설정(한 번): `python3 scripts/vibe.py configure --apply`
- 요약/리포트 생성: `python3 scripts/vibe.py doctor --full`
- 검색: `python3 scripts/vibe.py search "<query>"`
- 영향도 분석: `python3 scripts/vibe.py impact <path>`
- 요약팩 생성: `python3 scripts/vibe.py pack --scope=staged|changed|path|recent --out .vibe/context/PACK.md`

## 커스텀(레포별)
- 설정은 `.vibe/config.json`에서 합니다 (`exclude_dirs`, `include_globs`, `quality_gates`, `checks` 등).
- 커맨드 기반 체크(선택): `.vibe/config.json`의 `checks.doctor` / `checks.precommit`에 원하는 명령을 추가할 수 있습니다.

## 출력물
- DB: `.vibe/db/context.sqlite` (git ignore)
- 리포트: `.vibe/reports/*` (git ignore)
- 최신 요약: `.vibe/context/LATEST_CONTEXT.md` (자동 갱신)

## Git hook (선택)
`.git`이 있는 클론에서만:
- `python3 scripts/vibe.py hooks --install`

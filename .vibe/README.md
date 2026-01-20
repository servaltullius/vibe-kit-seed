# vibe-kit (Skyrim_Translator_v6)

이 폴더는 “에이전트/유저가 프로젝트를 잃지 않게” 도와주는 로컬 도구함입니다.

## 빠른 시작
- 한 방 진단(권장): `python scripts/vibe.py doctor --full`
- (Windows) `scripts\\vibe.cmd doctor --full`
- 감시(선택): `python scripts/vibe.py watch`

## 출력물
- DB: `.vibe/db/context.sqlite` (git ignore)
- 리포트: `.vibe/reports/*` (git ignore)
- 최신 요약: `.vibe/context/LATEST_CONTEXT.md` (자동 갱신)

## Git hook (선택)
`.git`이 있는 클론에서만:
- `python scripts/vibe.py hooks --install`

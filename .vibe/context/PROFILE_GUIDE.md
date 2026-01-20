# PROFILE_GUIDE (vibe-kit)

This project is primarily a Windows WPF app + Core library.

## Recommended (Windows) tooling
- PerfView (ETW) for CPU sampling
- `dotnet-trace` for .NET trace collection (optional)

### dotnet-trace quick start
1) Install (once):
   - `dotnet tool install --global dotnet-trace`
2) Run the app (or a target process), find PID, then collect:
   - `dotnet-trace collect --process-id <PID> --duration 00:00:20 -o trace.nettrace`
3) Open `trace.nettrace` in Visual Studio / PerfView.

## vibe-kit integration
- `python3 scripts/vibe.py doctor --full --profile` will only summarize existing logs under `.vibe/reports/`.
- No source-code injection is performed.

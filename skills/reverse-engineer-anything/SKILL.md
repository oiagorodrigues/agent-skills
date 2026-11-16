---
name: reverse-engineer-anything
description: Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA, and build agent environments (AgentEnv bundles) of web applications from a live instance or a capture. Use shipped-artifact or requested runtime evidence to explain features, compare versions, decompile code, or guide a reconstruction. Use when the user asks to reverse engineer, decompile or explain a shipped binary, app, package, firmware or web app, to compare its versions, or to build an AgentEnv bundle. Skip REA for ordinary source-repository architecture analysis.
metadata:
  version: "60"
---

# REA

Use REA when a claim depends on a shipped binary or package, decompilation,
requested runtime evidence, or comparison with
behavior not established by available source. For ordinary analysis of a
complete source repository, use normal repository tools and do not run REA
readiness or provider commands.

## Connect only when needed

Installing this skill supplies instructions; it does not register the REA MCP
server, install analysis engines, or add tools to an already-running agent.
The exception is a Claude Code or Codex plugin install: the plugin bundles
this skill and registers its own `rea` server, outside the state that
`rea setup` and `rea doctor` manage.

If REA tools are available and their registration is not known to be stale,
proceed directly to the target. Do not run diagnostics or setup before every
investigation. Use the connected server's actual tool list and input schemas;
a skill installed from repository main may describe capabilities absent from
an older npm release. Keep complete inline Evidence when that server does not
advertise retained references.

If tools are absent, a call is blocked by the client, or a required provider is
unavailable, read [connection and recovery](references/connection-and-recovery.md).
Diagnose the observed blocker, continue useful supported work, and resume the
original task after repair. Client approval, shell PATH, registration and engine
availability have different remedies; avoid repeating setup for all of them.
If the host times out without a REA result, do not repeat the unchanged call or
assume work stopped. Read the recovery guide's deadline distinction before retrying.
If the MCP connection drops, retry that call once only when it is safe to
repeat or known not to have started. If it may already have changed the
target, or it fails again, tell the user and ask them to restart the MCP
client. If REA could not start its connection, retry once, then tell the user
and ask them to restart the MCP client. Do not retry a startup failure that
returns the same unchanged result. For plugin installs, follow
[plugin recovery](references/connection-and-recovery.md#rea-installed-as-a-client-plugin).
For setup-owned registrations, run `rea doctor` when REA could not start
or tools stay missing after that restart. For `cleanup_incomplete`, a retryable
capacity limit, or `configuration_invalid`, follow the recovery guide's ladder
before asking for a restart. Read that guide before a second repair attempt.

Choose the installation owner before repairing registration. Plugin installs use
[plugin recovery](references/connection-and-recovery.md#rea-installed-as-a-client-plugin);
only setup-owned registrations use the guide's
[registration repair plan](references/connection-and-recovery.md#repair-registration-when-needed).
A plugin-only doctor result of `missing` does not call for `rea setup`.

REA setup never installs or upgrades Node.js, npm, Homebrew, Java, Ghidra, IDA,
JADX, Kuna, Binwalk, or Unblob. Use existing prerequisites; do not install unrelated
software to repair MCP registration. For an unsupported client, use manual stdio
registration with an existing installation’s absolute runtime and entry script, or continue through the CLI.

For the CLI fallback when MCP tools are absent, REA package acquisition and
setup-owned configuration repair, read
[setup and CLI fallback](references/setup-and-cli-fallback.md).

## Route the target first

Choose the first tool from the target the user supplied. Use `open_binary` for
active-target native or archive workflows; target-free tools take their own
explicit path or endpoint and do not need it.

Read the route's entry in [per-route detail](references/per-route-detail.md)
before its first call: it holds prerequisites, environment variables, paging
and what an absent result does not prove.

- ASAR or extracted JavaScript/Electron tree: `analyze_javascript_application`.
- Archive/package member inventory (ZIP/APK/IPA/MSIX/AppX, DMG, PyInstaller executable): `open_binary`, then `inspect_artifact`.
- Bun `--compile` executable: `open_binary`, then `inspect_artifact`.
- Apple plist, Interface Builder, asset catalog or keyed archive resources: `open_bundle_resources`.
- Android APK code, classes, methods or incoming references: `inspect_android_package`.
- Managed PE/CLI assembly: `inspect_managed_artifact`.
- Firmware image: `inspect_firmware_regions`; `extract_firmware` when extraction is requested.
- ESP32-family app or bootloader image (`0xE9` magic): `inspect_artifact` without a provider.
- .NET NativeAOT PE/ELF: native Ghidra analysis.
- Native program behavior, live calls, instrumentation or command-run effects: the matching
  [native runtime workflow](references/runtime-observation.md#native-runtime-questions).
- User-owned browser page already open: `list_browser_targets`.
- Passive traffic capture of a SPA: pass the page origin and the API origins in `allowed_origins`.
- Browser action the agent must perform (click, type, navigate): `capture_browser_scenario`.
- Agent environment (AgentEnv bundle) of a web application: read [environments](references/environments.md) before recording.
- Task for a desktop application's exported environment: read
  [desktop application tasks](references/environments.md#tasks-for-a-desktop-application-environment).
- Fiddler Everywhere traffic or a native `.saz` capture: read the
  [Fiddler workflow](references/runtime-observation.md#fiddler-everywhere-traffic-debugging).
- Retained HAR/SAZ/mitmproxy/qlog capture: `inspect_web_network_capture`.
- User-owned Electron runtime already open: `list_electron_targets`; `inspect_electron_fuses` before an electron-main Inspector attempt.
- Packet fields: `inspect_packet_fields`. Recorded packet captures: `inspect_packet_capture`. Address/DNS/SNI/protocol summaries: `inspect_pcap_capture`.
- Signal decoders: `inspect_signal_decoders`. Recorded logic/signal traces: `decode_signal_recording`.
- Local WebAssembly: `inspect_wasm_artifact`. Local APK/ZIP/AAB signing: `inspect_apk_signature`. Local EVM bytecode: `inspect_evm_interface`.
- Go build metadata: `inspect_go_binary`. Rust cargo-auditable metadata: `inspect_rust_binary`.
- Embedded CUDA/HIP code objects: `inspect_gpu_code_objects`. GGUF or safetensors model: `inspect_model_artifact`.
- Unity IL2CPP `global-metadata.dat`: `inspect_il2cpp_metadata`.
- PE Authenticode: `inspect_pe_certificates`. PE imports: `inspect_pe_imports`. PE TLS callbacks and load configuration: `inspect_pe_load_config`. PE resources: `inspect_pe_resources`. PE/ELF exports: `inspect_native_exports`.
- ELF/PE/Mach-O hardening: `inspect_binary_hardening`. ELF notes: `inspect_elf_notes`. Linux ELF layout: `inspect_binary_layout`. Linux x86-64 ELF core: `inspect_recorded_crash`.
- Apple `.ips` crash report: `inspect_apple_ips`. Linux kernel module: `inspect_kernel_module`.
- CPython `.pyc`: `inspect_python_pyc`. Erlang `.beam`: `inspect_erlang_beam`. SQLite snapshot: `inspect_sqlite_database`.
- Native executable, library or analysis database: `open_binary`, then focused analysis tools.
- IDA (`provider_id: "ida"`), Kuna (`provider_id: "kuna"`) or a Ghidra startup timeout: read that section of the detail file first.

If the user says only "my app" without a name, path, or target already selected
for this task, ask which app before searching for artifacts. Paths in unrelated
saved reports and nearby test fixtures do not select the user's target. Resolve
an actual human-readable app name to one clear installed artifact when possible;
ask when matches are ambiguous. Never choose an example app on the user's behalf.

In a target-free session, use `open_binary` to bind any archive/package or
native target whose analysis tool operates on the active target. Do not call an
unadvertised tool; inspect `binary_session` with `{}` and its
`result.tool_availability` for availability reasons and remediation. Expand each
group's `names` into entries, inheriting the inventory-level client requirements
unless the group overrides them. The grouped name union is the complete tool
inventory; use `tools/list` for canonical tool schemas. The default summary keeps
each provider candidate's availability and target-support status, code and
reason; `omitted_fields` lists what it leaves out. Request `{"detail": "complete"}`
only when you need an unavailable candidate's remediation, provider
diagnostics, candidate capability sets, or tool surface, effect and annotation
flags; in those closed flag vocabularies, listed
flags are true and omitted known flags are false. Provider candidate facts
describe possible providers, while top-level session capabilities describe the
current route and `analysis_provider_binding` names the selected provider. Do
not treat those scopes as interchangeable.

## Work summary-first

Start with the default result and use its inline Evidence and graph context.
For a JavaScript application or ELF layout whose size is unknown or large,
call `analyze_javascript_application` or `inspect_binary_layout` with
`"detail": "summary"`, then inspect the retained `parent_evidence_id` with
`inspect_analysis_view`. Over MCP, `analyze_function` is summary-first without
a flag: its default reply is the summary, and the complete dossier stays
retained under `parent_evidence_id` for facet paging. Pass that ID as a
`retained-evidence` reference to `compare_functions`, or inside
`match_native_functions` `left_observations`/`right_observations` or
`build_call_path.functions`; request `"detail": "complete"` only when the
dossier must travel inline.
Use the same exact-reference form in other advertised logical Evidence inputs,
including optional sources, arrays and nested sources across domains. Each
source can independently be inline or retained; preserve its source identity,
coverage, partial facts and unknowns. A summary or inspection page has its own
Evidence ID: use `normalized_result.parent_evidence_id` when the consumer needs
the complete source. For portable CLI follow-ups, commands advertising
`--evidence-bundle` resolve references from that selected exported bundle.
See [Evidence composition](references/evidence-workflows.md) for scope and
recovery; file selectors are supported only where explicitly advertised.
Page module identities and select the returned `node_id` before requesting an
item; a single file path can represent several graph roles. Do not repeat an
identical analysis or rejected call without a changed input or resolved blocker.
Recheck session state when a lifecycle change makes that status useful.
Make a focused follow-up only when the
returned result leaves a specific question unanswered.

If MCP reports `resource_constraint` with `details.resource: "transport"`, the
retained parent ID is unknown, or a client truncates a result, read
[large results](references/large-results.md) before the next call.

Every conclusion must distinguish observations, inferences, and unknowns. Cite
Evidence IDs, preserve limitations and incomplete coverage, and never imply
that static analysis observed execution. Runtime requests execute the declared
target and lifecycle; do not broaden the target or action beyond those fields.

Within the user's requested investigation, call available analysis tools
directly. REA does not require permission grants or per-call approval flags.
The agent client can independently require approval. Follow the declared request
scope and the host's actual access requirements; use the recovery guide for an
observed client-policy rejection.

## Plan broader investigations

For requests that span multiple features or subsystems, follow the staged
workflow in [broader investigations](references/broader-investigations.md).

## Read only the relevant guide

- Native binaries, managed assemblies, archives, and extraction:
  [references/native-and-artifacts.md](references/native-and-artifacts.md)
- ASARs, extracted JavaScript, feature tracing, and version comparison:
  [references/javascript-applications.md](references/javascript-applications.md)
- Android APK declarations, classes, methods, and static references:
  [references/android-applications.md](references/android-applications.md)
- Native instrumentation, debugger and process capture; browser/Electron
  observation; static/runtime comparison:
  [references/runtime-observation.md](references/runtime-observation.md)
- Evidence paging, comparisons, residual unknowns, and verification:
  [references/evidence-workflows.md](references/evidence-workflows.md)
- Agent environments (AgentEnv bundles) of a web application, recorded from
  a live instance or a HAR:
  [references/environments.md](references/environments.md)
- Tasks for a desktop application's exported environment:
  [references/environments.md](references/environments.md#tasks-for-a-desktop-application-environment)
- Per-route prerequisites, IDA, Kuna and Ghidra startup timeouts:
  [references/per-route-detail.md](references/per-route-detail.md)
- CLI fallback and setup boundaries:
  [references/setup-and-cli-fallback.md](references/setup-and-cli-fallback.md)
- Transport limits, unknown parent IDs and truncated results:
  [references/large-results.md](references/large-results.md)
- Staged multi-feature investigations:
  [references/broader-investigations.md](references/broader-investigations.md)

## Finish the task

Explain findings in plain language and tie them to returned evidence. When the
user asks to build something, use normal coding tools and separate observed
behavior from design choices. Close an opened native session with
`close_binary` when its engine is no longer needed. Evidence references and Unknown
history remain in memory on the same MCP connection. End the investigation with
`reset_investigation`; supply `save_path` to checkpoint the complete bundle before
clearing. Import the saved bundle to restore original references and Unknown
history in a new process. Retention is bounded and is not automatic persistence.

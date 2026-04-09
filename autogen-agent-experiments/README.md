# AutoGen / AG2 Experiments

This folder contains a collection of AG2 and AutoGen-based experiments, prototypes, and UI-backed demos.

## Main Subprojects
- `ag2-tool-calling-experiments/`: simple AG2 tool-calling and calculation experiments
- `ag2-supervisor-sentiment-chat/`: AG2 chat service with sentiment detection and supervisor takeover
- `ag2-sentiment-based-supervisor-handoff/`: service chat demo that hands conversations to a supervisor when sentiment drops
- `ag2-supervisor-barge-in-chat/`: supervisor intervention demo for dissatisfied customer chats
- `ag2-java-escalation-chat-demo/`: AG2-backed escalation demo with Java client code
- `hcm-wrapper-chat-ui/`: AutoGen chat UI backed by an HCM wrapper or external completion service
- `google-assisted-hcm-wrapper-chat/`: HCM wrapper chat with research or search assistance
- `customer-support-multi-agent-simulation/`: scripted customer-support simulation across multiple personas
- `oracle-field-service-support-agent/`: field-service support workflow demo with knowledge-base and live-agent transfer concepts
- `generated-artifacts/`: generated output such as charts and one-off artifacts

Each main subproject now includes its own `README.md` with a short description and file guide.

## Notes
- This is an experiments folder, not a single cohesive application.
- Some scripts depend on local models, private systems, or internal endpoints.
- Several demos should be reviewed and scrubbed for hardcoded credentials or internal URLs before any public push or repo split.
- Generated or local-only folders such as `.cache/` and `.idea/` are present for convenience.

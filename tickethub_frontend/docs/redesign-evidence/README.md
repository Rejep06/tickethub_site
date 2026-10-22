# Evidence

Unit, source and translation logs are actual command output. Build/lint/components/E2E logs record tool-startup failures, not passing tests. `typecheck-excerpt.log` is an explicitly truncated extract.

`isolated-layout.json` comes from actual Chromium rendering of an offline JSX-to-HTML layout harness using the application CSS and component structure. External libraries and hooks were stubbed in that harness only. It is NOT a Next/React/Django runtime check. The harness and its stubs are not part of the application.

# BDD Features (Pilot)

This directory holds human-readable Gherkin scenarios for user-visible behaviors.

## Source of truth hierarchy

1. `DEFINITION_OF_DONE.md` is the primary acceptance source.
2. `FEATURES.md` is the implemented feature inventory.
3. `features/*.feature` expresses acceptance behavior in Gherkin.

## Authoring rules

- Keep scenarios business-readable and stable over time.
- One primary outcome per scenario (a single `Then` line).
- Use layered tags so not all scenarios become browser E2E tests:
  - `@ui` for UI/browser behavior
  - `@pipeline` for script/pipeline behavior
  - `@accessibility` for accessibility behavior
- Include traceability comments in each feature file:
  - `DEFINITION_OF_DONE.md` section reference(s)
  - `FEATURES.md` section reference(s)

## Maintenance rule

When behavior changes, update the related document section(s) and the affected
scenario(s) in the same pull request.

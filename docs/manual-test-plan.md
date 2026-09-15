# Manual test plan

## Start
```bash
cp .env.example .env
docker compose up --build
```

## Verify
1. Open `http://localhost:3000`.
2. Confirm the health pill loads.
3. Create a session.
4. Ask a grounded product/growth question.
5. Confirm citations appear.
6. Ask a follow-up question in the same session.
7. Create a second session and confirm isolation.
8. Ask for a Ship 30 essay.
9. Confirm the markdown artifact opens in the Artifact Viewer.
10. Ask for an HTML/CSS artifact.
11. Confirm the iframe renders and unsafe script behavior is stripped.
12. Trigger transcript reindexing.
13. Confirm `/health` and `/api/providers` still respond.

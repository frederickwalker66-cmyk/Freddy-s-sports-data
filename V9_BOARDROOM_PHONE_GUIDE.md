# V9 Phone Boardroom — read-only public interface and protected voice entry

The optional page `docs/boardroom.html` adds a responsive, phone-friendly visual executive boardroom linked from the existing dashboard. It has named specialist cards, an explicit CEO seat/policy, live **GitHub Actions workflow-status metadata** fetched read-only from public REST endpoints, and a local-only *discussion draft* for exact proposed picks.

### Current capabilities

- Named employees: Bella (Command Center), David (Sports Data), Cassidy (Sharp Edge), Roger (Parlays), Sarah (Risk), Adam Stone (Audit); three women, three men. Clothing direction for forthcoming actual images: everyday hoodies, button-downs, casual sweaters, blouses and jeans. Initials circles are **placeholders**, not realistic human video avatars.
- The CEO uses the separate cloned Freddy ElevenLabs voice, not an employee voice.
- Each employee's distinct voice and one-at-a-time handoff are already configured in ElevenLabs. The public boardroom links to the **signed-in** ElevenLabs Agents workspace; it does not embed public, unauthenticated speaking widgets.
- Live workflow *operational status* for existing GitHub schedule preflight, watchdog, and six-person pregame meeting; uses only public GitHub GET endpoints, no token and no new sports-data provider calls.
- Local in-session pick drafts are **not** saved, sent, signed, published, voted or placed. Each displays 0/6 authenticated votes and HOLD.
- Upstream V9 GitHub reports remain accessible via the direct Actions link and include the six-role per-pick unanimous policy.

### Restrictions essential for safe deployment

This Pages site is **public**, as is the GitHub repository. The ElevenLabs agents currently have authentication disabled and blank origin allowlists. Publishing the six agent IDs inside a public embedded widget could allow anyone to consume the owner's usage credits. This interface deliberately DOES NOT expose the agent IDs, ElevenLabs API keys, mic controls or public widget and does not request microphone access.

The public GitHub Actions API can be rate-limited or unavailable. The UI fails closed to 'Unavailable' and never guesses a result. Green CI is NOT an independently certified Sharp Edge wager; native frozen Champion-001 output, executable DraftKings offers, market-level calibration and employee vote authentication remain missing.

A fully private live audiovisual conference needs an authenticated hosting layer, session access control and per-agent identity verification, and separately tested avatar animation. Do not use an unprotected GitHub Pages voice widget for the user.

### Navigation

On the public command center, select **V9 Virtual Boardroom**. If GitHub Pages is deployed, the expected page is:

https://frederickwalker66-cmyk.github.io/Freddy-s-sports-data/boardroom.html

That URL must be tested after Pages deployment; a source file alone does not prove the page is live.

### Validation

`python -m unittest discover -s tests -p 'test_v9_boardroom_public.py' -v` checks roster, unique HTML IDs, explicit HOLD decisions, no outbound wagers or GitHub writes and no public ElevenLabs agent/widget credentials. The preexisting GitHub Pages publish workflow validates the boardroom tests before deploying with its regular public dashboard files. It does not call paid sportsbook/voice APIs.

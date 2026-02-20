# ReviewerCalls

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Curated self-nomination calls for reviewers and committee members of
CCF- and CORE-ranked conferences.

**[Browse the live website &rarr;](https://ZhongkuiMa.github.io/ReviewerCalls/)**

## What This Is

ReviewerCalls aggregates publicly available reviewer self-nomination pages from 321 CCF- and CORE-ranked computer science conferences. If a conference is accepting volunteer reviewers, program committee members, or artifact evaluation committee members, we aim to list it here.

Automated discovery runs weekly. Each candidate is manually verified before appearing on the website.

## How It Works

1. **Discovery** -- An automated system searches conference websites for reviewer nomination pages weekly
2. **Validation** -- LLM-powered validator filters false positives (code of conduct, visa info, etc.)
3. **Verification** -- Each candidate is manually reviewed to confirm it is a genuine self-nomination page
4. **Publication** -- Verified entries appear on the website, updated automatically

## What Qualifies

A page qualifies only if it explicitly invites individuals to apply or nominate themselves for:
- Reviewer / External Reviewer
- Program Committee (PC) / Senior Program Committee (SPC)
- Area Chair (AC) / Senior Area Chair (SAC)
- Artifact Evaluation Committee (AEC)
- Emergency Reviewer

Out of scope: invitation-only calls, chair-nominated processes, private or login-required pages.

## Contributing

Found a reviewer call we're missing? See [CONTRIBUTING.md](CONTRIBUTING.md) for how to submit it.

## Disclaimer

**This website is an information aggregation service only.** All information is collected from publicly available sources and may be outdated, incomplete, or incorrect. Users are responsible for:
- **Verifying all information** with official conference websites before taking action
- **Checking deadlines and eligibility requirements** directly with conference organizers
- **Confirming that links are current** and lead to active nomination pages

We make no warranties about the accuracy, completeness, or timeliness of the information provided. Always consult official conference sources for authoritative information.

## Acknowledgments

- Conference data sourced from [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines) -- a comprehensive CCF conference deadline tracker
- Inspired by [jiahaoli57/Call-for-Reviewers](https://github.com/jiahaoli57/Call-for-Reviewers) -- a community-curated list of reviewer calls for AI conferences and journals

## Support

If you find this project useful and successfully land a reviewer position, consider buying me a coffee! ☕

<a href="https://www.buymeacoffee.com/zhongkuimac">
  <img alt="Buy Me A Coffee" src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="50px" style="height: 50px;">
</a>

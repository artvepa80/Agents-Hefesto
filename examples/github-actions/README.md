# Hefesto GitHub Actions templates

Two workflow templates for running `hefesto pr-review` as a PR check.
Pick the one that matches your use case and copy it to
`.github/workflows/hefesto-pr-review.yml` in your repository.

## Which one should I use?

| Template                          | Dedup | Onboarding cost | Best for             |
|-----------------------------------|-------|-----------------|----------------------|
| `hefesto-pr-review-simple.yml`    | No    | 1 file, copy    | Small repos, trials  |
| `hefesto-pr-review-deduped.yml`   | Yes   | 1 file, copy    | Production use       |

**Rule of thumb:** start with the simple template to validate that
Hefesto sees your code correctly. Switch to the deduped template once
you have a PR with multiple push events — without dedup, every push
appends another batch of identical comments to the same lines.

## How dedup works

Every Hefesto finding carries a deterministic `dedup_key` computed as
`sha256(relative_path | line | issue_type | normalized_message)`. The
deduped template:

1. Runs `hefesto pr-review` with no `--post` to get JSON.
2. Calls `gh api ... /pulls/<N>/comments` to list existing comments.
3. Extracts `dedup_key=sha256:<hex>` from the HTML marker at the top of
   each comment body.
4. Filters new findings by set-subtract of existing keys.
5. Posts only the truly new findings via `gh api`.

The dedup logic lives in `jq`, not Hefesto — Hefesto's job is to emit
stable keys. This separation keeps the Python core network-free and
lets you replace the posting layer without patching Hefesto.

## Troubleshooting

- **`gh api` 422 errors on `line`**: make sure the finding's line
  number falls inside a changed hunk on the head commit. The deduped
  template already filters with `.in_hunk == true`; the simple
  template skips non-hunk findings inside `post_findings`.
- **Comments keep duplicating**: you are using the simple template.
  Switch to the deduped one.
- **No comments posted**: check the `Generate findings JSON` step
  output — if `findings` is empty, there is nothing to post.

---
name: vercel-troubleshooter
description: Diagnoses a site hosted on Vercel that is down or unreachable. Walks from deploy status to runtime logs, DNS, per-IP connectivity and traceroute, and runs Vercel Support's official debug script from a reviewed local copy. Use when a Vercel site shows ERR_TIMED_OUT, connection refused or 404/5xx, when the user says "site fora do ar", when DNS is in doubt, or when preparing a Vercel support ticket.
---

# Vercel troubleshooter

Use this when someone reports that a site on Vercel is down, slow to connect or unreachable, when a deploy looks fine but users can't load the site, or when Vercel support asks for diagnostics. Work through the steps in order and stop at the first one that explains the problem.

In the commands below, `$DOMAIN` is the custom domain (e.g. `example.com`), `$TEAM` the Vercel team slug and `$PROJECT` the Vercel project. Find the last two with `vercel project ls` or in `.vercel/project.json`. Check the project's own notes or memory for setup facts (DNS host, expected redirects) before starting.

## Steps

1. **Is it only this network?** Ask whether the site loads on mobile data or from another network, and whether other sites on Vercel load from the affected network. If only the affected network fails, ask the user to restart the modem/router before anything else. In the example case below, that alone fixed a timeout that looked like ISP routing.

2. **Deploy status.** `vercel ls $PROJECT --scope $TEAM` and `vercel inspect <production url> --scope $TEAM`. Check that the latest production deploy is Ready and lists the custom domains under Aliases.

3. **Runtime logs with status codes.**

   ```bash
   vercel logs <production url> --scope $TEAM --since 1h --json \
     | jq -r '[.timestamp, .domain, .requestPath, .responseStatusCode] | @tsv'
   ```

   200s on `$DOMAIN` from other visitors mean the server is fine and the problem is between the user and Vercel.

4. **DNS.** Find who hosts the zone, then compare the authoritative answer with public resolvers:

   ```bash
   dig +short NS $DOMAIN
   dig +short A $DOMAIN @<first nameserver>
   for r in 8.8.8.8 1.1.1.1 9.9.9.9; do dig +short A $DOMAIN @$r; done
   ```

   If the nameservers aren't Vercel's, the DNS records list in the Vercel dashboard is empty by design and changes are made at the DNS host. If the authoritative nameserver still shows the old value after an edit, the change wasn't saved; it isn't propagation. Public resolvers can lag by the record's TTL.

5. **Connectivity per IP.** Separates a dead site from an unreachable IP. `76.76.21.21` is Vercel's older apex IP, still supported; `216.198.79.1` is the newer recommended one:

   ```bash
   curl -sv -m 15 -o /dev/null https://$DOMAIN/ 2>&1 | grep -E "Trying|Connected|HTTP/|timed out"
   for ip in 76.76.21.21 216.198.79.1; do
     curl -s -m 10 -o /dev/null -w "%{http_code} via $ip\n" --resolve $DOMAIN:443:$ip https://$DOMAIN/ || echo "timeout via $ip"
   done
   ```

   A timeout on one IP and a 200 on another means the network path to that IP is broken, not the site.

6. **Route.** UDP traceroute needs no `sudo` on macOS; the TCP mode (`-P tcp`) does. Compare a failing IP with a working one and look up the hops' owners:

   ```bash
   for ip in 216.198.79.1 76.76.21.21; do traceroute -n -w 2 -q 1 -m 20 $ip; done
   whois <hop ip> | grep -iE "^(owner|OrgName|aut-num):"
   ```

   The hop where the two routes split, or after which only `*` appears, names the network dropping the traffic. Routers often don't answer traceroute, so the `*` lines only mean something next to a working route through the same hops.

7. **Vercel Support debug script.** Vercel support asks for the output of https://github.com/vercel-support/vercel-connect-debug, normally as `curl -s https://raw.githubusercontent.com/vercel-support/vercel-connect-debug/main/vercel-debug.sh | bash | tee vercel-debug.txt`. Never pipe it from the internet. Use the reviewed copy next to this file:
   1. Run `~/.agents/skills/vercel-troubleshooter/scripts/check-upstream.sh`. Within 7 days of the last review it exits 0 and does nothing. Older than that, it downloads the upstream script and compares SHA-256: unchanged bumps `verified_at` in `scripts/upstream.txt`; changed exits 2 and prints a diff. Read the whole diff, confirm it only does read-only diagnostics, and only then run it again with `--accept`. `--force` re-checks regardless of age.
   2. Have the user run it **in their own terminal, on the affected network** (it reads the domain from `/dev/tty`, so the ! prefix in Claude Code won't work):

      ```bash
      bash ~/.agents/skills/vercel-troubleshooter/scripts/vercel-debug.sh | tee ~/vercel-debug.txt
      ```

      Enter the bare domain when asked, without `https://`. The output includes the user's public IP and approximate location from ipinfo.io, which is fine to send to Vercel support but shouldn't be pasted anywhere public.

## Reporting

- Vercel support: https://vercel.com/help, under the right team. Include the timestamps, the per-IP curl results, both traceroutes with hop owners, and `vercel-debug.txt`.
- If Vercel says the traffic never reaches them, open a ticket with the ISP with the same evidence and ask for escalation to the network/backbone team.
- Until the path is fixed, point the apex A record at an IP that works from the affected network (step 5), and say so in the reply.

## Permissions

In auto mode, `curl` against a production site, `vercel curl`, `gh pr merge` and closing PRs may be blocked. Don't work around a denial; give the user the exact command to run with the ! prefix (no space before it), or ask them to allow it in `/permissions`.

## Example case

A user's browser showed `ERR_TIMED_OUT` for a site whose production deploy was Ready. The runtime logs showed other visitors getting 200s, and DNS at a third-party host (so the Vercel DNS list was empty) resolved correctly everywhere. `curl` to the apex IP `216.198.79.1:443` timed out, while `--resolve` through `76.76.21.21` returned 200 and the `.vercel.app` alias connected through another Vercel IP. The UDP traceroutes to both IPs went through the same five ISP hops, and only the one toward `216.198.79.1` stopped there.

The apex A record was moved to `76.76.21.21` as a workaround, which brought the site back for that user. Vercel support confirmed the traffic never reached them, and mobile data worked from the same place. Restarting the user's modem then fixed the path to `216.198.79.1`, so the cause was the user's modem or connection. Lessons: ask for the modem restart and the mobile-data test first (step 1), and once the path works again, decide whether to move the A record back to the recommended IP.

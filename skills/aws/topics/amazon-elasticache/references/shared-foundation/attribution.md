# Attribution

The upstream skill tagged every resource it created with skill and model attribution tags (`managed_by`, `skill`, `skill_version`, `created_by`, `generation_model`) and set the `AWSSkill-ElastiCache` user-agent app ID (`AWS_SDK_UA_APP_ID`) on every call. This port drops both: don't add attribution tags or a skill user-agent to commands, SDK code, scripts or IaC. Tag resources with the user's own conventions (for cost allocation, `Environment`, `Application`, `Owner`; see `monitoring/cost-reporting.md`).

If an AWS Organizations tag policy rejects a tag, remove the conflicting tag and tell the user; tagging never blocks a create.

Don't use key prefixes in cached data, synthetic commands, hidden keys or outbound beacons to mark a cache.

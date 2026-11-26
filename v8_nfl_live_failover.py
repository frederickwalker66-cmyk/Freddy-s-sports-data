"""Provider-neutral failover; backup must supply independently normalized evidence."""
def usable(report):
    return (isinstance(report,dict) and report.get("status")=="SOURCE_RESPONSE_RECEIVED"
            and bool(report.get("games")) and not report.get("errors")
            and all(g.get("state")=="pre" or g.get("boxscore_available") is True
                    for g in report["games"]))

def collect_with_failover(primary, backup=None):
    attempts=[]
    last=None
    for name,provider in (("primary",primary),("backup",backup)):
        if provider is None:
            attempts.append({"provider":name,"status":"NOT_CONFIGURED"})
            continue
        try:
            report=provider()
            if isinstance(report,dict):
                last=report
            if usable(report):
                return dict(report,provider_attempts=attempts+[{"provider":name,"status":"RESPONSE_RECEIVED"}],
                            freshness_verified=False)
            attempts.append({"provider":name,"status":"INCOMPLETE"})
        except Exception as exc:
            attempts.append({"provider":name,"status":type(exc).__name__})
    return dict(last or {"games":[]},status="HOLD",provider_attempts=attempts,
                freshness_verified=False)

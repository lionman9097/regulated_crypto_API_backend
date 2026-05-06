from metrics.prometheus import get_metrics_snapshot


class KPICollector:
    def collect(self) -> dict:
        return get_metrics_snapshot()


kpi_collector = KPICollector()

ROLES=('admin','analyst','viewer')
STATES=('queued','running','done','failed')
ZONES=('冷藏','冷冻','常温对照')
SAMPLE_SOURCES=('manual','auto')
CALC_STATES=('pending','published','failed')
ZONE_THRESHOLDS={'冷藏':4.0,'冷冻':-18.0,'常温对照':25.0}
DEFAULT_MAX_GAP=10

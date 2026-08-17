def percent_change(previous,current):
    if previous is None or current is None: return None
    if previous==0: return None if current==0 else float("inf")
    return (current-previous)/previous*100.0

def subject_timeline(subject):
    rows=[]; previous=None
    studies=subject.timepoints.prefetch_related("jobs__result").order_by("timepoint_order","study_date")
    for study in studies:
        completed=[j for j in study.jobs.all() if j.status=="COMPLETED" and hasattr(j,"result")]
        result=completed[-1].result if completed else None; volume=result.whole_tumor_cm3 if result else None
        warning=None
        if previous:
            changes=[]
            if previous["study"].hospital_code!=study.hospital_code: changes.append("병원")
            if previous["study"].equipment_code!=study.equipment_code: changes.append("장비")
            if changes: warning=f"{'·'.join(changes)} 변경 구간: 직접 비교 시 주의가 필요합니다."
        rows.append({"study":study,"volume_cm3":volume,"delta_cm3":None if not previous or volume is None or previous["volume"] is None else volume-previous["volume"],"change_percent":None if not previous else percent_change(previous["volume"],volume),"comparison_warning":warning})
        previous={"study":study,"volume":volume}
    return rows

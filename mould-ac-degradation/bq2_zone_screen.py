"""Read-only BQ2 zone QA and July-August inspection screening.

Shared feature definitions and estimators come from the F3-Z1 first pass.
No upstream cleaning, weather refresh or shared-helper change is performed.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

import f3z1_audit as audit
import f3z1_first_pass as model

FLOORS = range(3, 8)
ZONES = [1, 2, 4, 5]
PERIOD = pd.date_range(audit.START, audit.END, freq="min", name="Date")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def column_spec(columns, zone):
    return {"ac": [c for c in columns if c.startswith(f"z{zone}_AC") and c.endswith("(kW)")],
            "temp": f"z{zone}_S1(degC)", "rh": f"z{zone}_S1(RH%)", "plug": f"z{zone}_Plug(kW)"}


def valid_masks(frame, spec):
    a = frame[spec['ac']]
    ac = (np.isfinite(a) & a.ge(0)).all(axis=1)
    t, r, p = frame[spec['temp']], frame[spec['rh']], frame[spec['plug']]
    env = np.isfinite(t) & t.between(15, 40) & np.isfinite(r) & r.between(0, 100)
    return pd.DataFrame({"ac": ac, "environment": env, "joint": ac & env,
                         "energy": ac & np.isfinite(p) & p.ge(0)})


def flatline_minutes(frame, fields):
    valid = frame[fields].notna().all(axis=1)
    same = frame[fields].eq(frame[fields].shift()).all(axis=1) & valid & valid.shift(fill_value=False)
    groups = (~same).cumsum()
    sizes = valid.groupby(groups).sum()
    return int(sizes.max()) if len(sizes) else 0


def audit_and_features(root, weather, helpers, output_dir):
    """Complete the quality pass and construct features, without fitting any models."""
    root, output_dir = Path(root), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    hourly_path = root / 'data-cleaning/outputs/analytics/zone_hourly.csv'
    quality_path = root / 'data-cleaning/outputs/analytics/data_quality.csv'
    hourly = pd.read_csv(hourly_path, parse_dates=['Date'])
    assert not hourly.duplicated(['floor', 'zone', 'Date']).any()
    quality = pd.read_csv(quality_path)
    sources = [hourly_path, quality_path, root/'data-cleaning/outputs/analytics/removed_readings.csv',
               root/'baseline/data/bangkok_era5_hourly_2018-2019.csv',
               root/'mould-ac-degradation/bq2_utils.ipynb', root/'baseline/humidity_risk_baseline.py',
               root/'data-cleaning/main.ipynb']
    timelines, channels, sensor_rows, zone_rows, reconciliations, gaps = [], [], [], [], [], []
    features = {k: [] for k in ['daily_features', 'event_features', 'steady_on_features', 'event_eligibility']}
    expected_hours = pd.date_range(audit.START, '2019-12-31 23:00', freq='h', name='Date')
    assert weather.index.is_unique and weather.reindex(expected_hours).notna().all().all()
    for floor in FLOORS:
        frames = {}
        for kind, folder in [('raw','data'), ('clean','data-cleaning/outputs/clean')]:
            parts = []
            for year in [2018, 2019]:
                path = root/folder/f'{year}Floor{floor}.csv'
                sources.append(path)
                header = pd.read_csv(path,nrows=0).columns
                specs = {z: column_spec(header,z) for z in ZONES}
                needed = [c for s in specs.values() for c in s['ac']+[s['temp'],s['rh'],s['plug']]]
                data = pd.read_csv(path,usecols=['Date']+needed)
                date_text = data.pop('Date')
                # Match the explicit source-format rule in upstream cleaning.
                fmt = '%d/%m/%y %H:%M' if date_text.str.contains('/').any() else '%Y-%m-%d %H:%M:%S'
                dates = pd.to_datetime(date_text, format=fmt, errors='coerce')
                valid_dates = dates[dates.notna()]
                invalid_with_measurements = int(data.loc[dates.isna()].notna().any(axis=1).sum())
                row = dict(source=str(path.relative_to(root)), rows=len(data), invalid_timestamps=int(dates.isna().sum()),
                           date_format=fmt, invalid_rows_with_measurements=invalid_with_measurements,
                           duplicate_timestamps=int(valid_dates.duplicated().sum()), sorted=bool(valid_dates.is_monotonic_increasing),
                           first=str(dates.min()),last=str(dates.max()),
                           off_minute_grid=int((dates.notna() & dates.ne(dates.dt.floor('min'))).sum()))
                timelines.append(row)
                if invalid_with_measurements or row['duplicate_timestamps'] or row['off_minute_grid'] or not row['sorted']:
                    raise ValueError(f'Ambiguous timestamps: {path.name}')
                # The known F6 truncated tail row has no date or measurements.
                # Record it above; exclude only such empty malformed rows locally.
                data = data.loc[dates.notna()]
                data.index = pd.DatetimeIndex(valid_dates,name='Date')
                parts.append(data)
            joined = pd.concat(parts)
            assert joined.index.is_unique and joined.index.isin(PERIOD).all()
            frames[kind] = joined.reindex(PERIOD)  # Absent tail slots remain NaN, never zeros.
        for zone in ZONES:
            label = f'F{floor}-Z{zone}'
            spec = column_spec(frames['clean'].columns,zone)
            assert len(spec['ac']) > 0
            fields = spec['ac']+[spec['plug'],spec['temp'],spec['rh']]
            raw, clean = frames['raw'][fields], frames['clean'][fields]
            observed = raw.where(raw.eq(clean))
            hh = hourly[(hourly.floor==floor)&(hourly.zone==zone)].set_index('Date').sort_index()
            assert hh.index.equals(expected_hours)
            assert hh.day_type.groupby(hh.index.normalize()).nunique().eq(1).all()
            masks = {name: valid_masks(data,spec) for name,data in [('raw',raw),('with_fills',clean),('without_fills',observed)]}
            scope = model.scoped(PERIOD)
            scope_raw = raw.where(pd.Series(scope,index=PERIOD),axis=0)
            sensor_max = {}
            for stream, cols in [('temperature',[spec['temp']]),('RH',[spec['rh']]),('paired',[spec['temp'],spec['rh']])]:
                maximum = flatline_minutes(scope_raw,cols)
                sensor_max[stream] = maximum
                sensor_rows.append(dict(zone_id=label,floor=floor,zone=zone,stream=stream,
                                        raw_scope_max_constant_minutes=maximum,
                                        raw_full_max_constant_minutes=flatline_minutes(raw,cols)))
            zero_meters = []
            for c in fields:
                a,b = raw[c],clean[c]
                log = quality[(quality.floor==floor)&(quality.column==c)].iloc[0]
                values = a[scope].dropna()
                if c in spec['ac'] and len(values) and values.eq(0).mean() >= .999:
                    zero_meters.append(c)
                channels.append(dict(zone_id=label,floor=floor,zone=zone,column=c,
                    full_raw_missing_pct=100*a.isna().mean(),full_clean_missing_pct=100*b.isna().mean(),
                    logged_missing_pct=log.final_missing_pct,
                    quality_log_missing_agrees=bool(abs(100*b.isna().mean()-log.final_missing_pct)<=.011),
                    scope_raw_missing_pct=100*a[scope].isna().mean(),scope_clean_missing_pct=100*b[scope].isna().mean(),
                    scope_newly_filled_minutes=int((a[scope].isna()&b[scope].notna()).sum()),
                    scope_replaced_minutes=int((a[scope].notna()&b[scope].notna()&a[scope].ne(b[scope])).sum()),
                    raw_scope_p01=values.quantile(.01),raw_scope_median=values.median(),raw_scope_p99=values.quantile(.99),
                    raw_scope_zero_pct=100*values.eq(0).mean(),upstream_note=str(log.note) if pd.notna(log.note) else ''))
            # Inspectable physical/placement flags. A suspect sensor is not a mechanical fault.
            sensor_reasons = []
            if (floor,zone)==(5,1): sensor_reasons.append('known unusually cold sensor; placement/calibration unresolved')
            invalid_temp = (raw[spec['temp']].notna() & ~raw[spec['temp']].between(15,40))[scope].sum()
            invalid_rh = (raw[spec['rh']].notna() & ~raw[spec['rh']].between(0,100))[scope].sum()
            if invalid_temp or invalid_rh: sensor_reasons.append('raw environmental values outside analysis validity bounds')
            if sensor_max['paired']>=60 or max(sensor_max['temperature'],sensor_max['RH'])>=1440:
                sensor_reasons.append('long exact raw sensor plateau; verify sensor before environmental ranking')
            meter_reason = 'near-all-zero raw AC meter(s): '+', '.join(zero_meters) if zero_meters else ''
            record = dict(zone_id=label,floor=floor,zone=zone,ac_meters=len(spec['ac']),
                          full_clean_joint_coverage_pct=100*masks['with_fills'].joint.mean(),
                          full_observed_joint_coverage_pct=100*masks['without_fills'].joint.mean(),
                          suspect_sensor=bool(sensor_reasons),sensor_reason='; '.join(sensor_reasons),
                          meter_mapping_review=bool(zero_meters),meter_reason=meter_reason,
                          raw_scope_invalid_temp_minutes=int(invalid_temp),raw_scope_invalid_RH_minutes=int(invalid_rh))
            for variant in ['with_fills','without_fills']:
                for year in [2018,2019]:
                    ix=scope & (PERIOD.year==year)
                    for stream in ['energy','environment','joint']:
                        record[f'{variant}_{year}_{stream}_coverage_pct']=100*masks[variant].loc[ix,stream].mean()
                for stream in ['ac','environment']:
                    rr=audit.true_runs(~masks[variant][stream]);rr=rr[rr.minutes>=1440].copy()
                    rr['zone_id'],rr['variant'],rr['stream']=label,variant,stream;gaps.append(rr)
            # Reconcile independently with the committed hourly export before fitting.
            minute=pd.DataFrame({'ac_kW':clean[spec['ac']].sum(axis=1,min_count=len(spec['ac'])),
                                 'plug_kW':clean[spec['plug']],'temp_C':clean[spec['temp']],'rh_pct':clean[spec['rh']]})
            expected=minute.resample('h').mean().where(minute.notna().resample('h').sum()>=48).round(2)
            for field in expected:
                mismatch=int(expected[field].isna().ne(hh[field].isna()).sum())
                diff=(expected[field]-hh[field]).abs()
                reconciliations.append(dict(zone_id=label,field=field,availability_mismatches=mismatch,
                                            value_mismatches=int(diff.gt(.0100001).sum()),max_abs_diff=diff.max()))
                assert mismatch==0 and not diff.gt(.0100001).any(),f'Hourly mismatch {label}/{field}'
            daily,events,humidity,eligibility,threshold=model.build_tables(raw,clean,hh,weather,helpers,column_spec=spec)
            record['frozen_threshold_kW']=threshold
            zone_rows.append(record)
            for name,data in zip(features,[daily,events,humidity,eligibility]):
                data['zone_id'],data['floor'],data['zone']=label,floor,zone
                features[name].append(data)
            print(f'{label}: quality checked; sensor_review={bool(sensor_reasons)}, meter_review={bool(zero_meters)}',flush=True)
        del frames
    result={k:pd.concat(v,ignore_index=True) for k,v in features.items()}
    result.update(zone_quality=pd.DataFrame(zone_rows),channel_quality=pd.DataFrame(channels),
                  timestamp_audit=pd.DataFrame(timelines),sensor_checks=pd.DataFrame(sensor_rows),
                  hourly_reconciliation=pd.DataFrame(reconciliations),major_gaps=pd.concat(gaps,ignore_index=True))
    for name,data in result.items(): data.to_csv(output_dir/f'{name}.csv',index=False)
    manifest=[dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=digest(p)) for p in sources]
    (output_dir/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return result


def load_evidence(output_dir):
    """Reload the completed QA stage without rereading all minute sources."""
    result={}
    for name in ['zone_quality','channel_quality','timestamp_audit','sensor_checks','hourly_reconciliation','major_gaps',
                 'daily_features','event_features','steady_on_features','event_eligibility']:
        data=pd.read_csv(Path(output_dir)/f'{name}.csv')
        for column in ['time','date','start','end']:
            if column in data: data[column]=pd.to_datetime(data[column])
        result[name]=data
    return result


def run_screen(evidence, output_dir, repetitions=2000):
    """Fit each eligible metric independently; retain every failed or held result."""
    output_dir=Path(output_dir)
    tables={'energy':evidence['daily_features'][evidence['daily_features'].eligible].copy(),
            'cooling':evidence['event_features'], 'moisture':evidence['steady_on_features']}
    targets={'energy':'ac_kWh','cooling':'cooling_rate_C_per_h','moisture':'indoor_w_gkg'}
    results, predictions, coefficients, candidates, cv_tables, checks, counts = [],[],[],[],[],[],[]
    for qa in evidence['zone_quality'].itertuples():
        label=qa.zone_id
        energy=tables['energy'].query('zone_id == @label and variant == "with_fills" and year == 2018')
        possible=[]
        if energy.date.nunique()>=20:
            for candidate, fields in model.ENERGY_CANDIDATES.items():
                try:
                    scores, cv=model.temporal_cv(energy,fields,'ac_kWh')
                except (ValueError,np.linalg.LinAlgError):
                    continue
                rec=dict(zone_id=label,candidate=candidate,**scores)
                candidates.append(rec);possible.append(rec)
        weather_options=[x for x in possible if x['candidate'] in ['temperature_activity','enthalpy_activity']]
        winner=min(weather_options,key=lambda x:(x['MAE'],x['candidate']))['candidate'] if weather_options else None
        for analysis,data in tables.items():
            subset=data[data.zone_id==label]
            target=targets[analysis]
            fields=(model.ENERGY_CANDIDATES[winner] if winner else []) if analysis=='energy' else (
                model.COOLING_FEATURES if analysis=='cooling' else model.MOISTURE_FEATURES)
            # Common unchanged-source observations should have identical features and targets.
            a=subset[subset.variant.eq('with_fills')].set_index('time')
            b=subset[subset.variant.eq('without_fills')].set_index('time')
            overlap=a.index.intersection(b.index)
            delta=(a.loc[overlap,fields+[target]]-b.loc[overlap,fields+[target]]).abs()
            maxdiff=float(delta.max().max()) if len(overlap) else np.nan
            assert not len(overlap) or maxdiff<1e-8
            checks.append(dict(zone_id=label,analysis=analysis,shared_rows=len(overlap),max_abs_input_or_target_difference=maxdiff))
            for variant in model.VARIANTS:
                tr=subset[(subset.variant==variant)&(subset.year==2018)].sort_values('time').copy()
                te=subset[(subset.variant==variant)&(subset.year==2019)].sort_values('time').copy()
                for year,part in [(2018,tr),(2019,te)]:
                    counts.append(dict(zone_id=label,analysis=analysis,variant=variant,year=year,rows=len(part),days=part.date.nunique()))
                record=dict(zone_id=label,floor=qa.floor,zone=qa.zone,analysis=analysis,variant=variant,
                            target=target,energy_specification=winner if analysis=='energy' else '',
                            reference_rows=len(tr),reference_days=tr.date.nunique(),eligible_evaluation_rows=len(te),
                            eligible_evaluation_days=te.date.nunique(),supported_rows=0,supported_days=0,
                            reference_weeks=tr.date.dt.to_period('W-SUN').nunique(),evaluation_weeks=0,
                            reportable=False,lead_eligible=False,status='',mean_residual=np.nan,residual_pct=np.nan,
                            bootstrap_low=np.nan,bootstrap_high=np.nan,bootstrap_percent_low=np.nan,bootstrap_percent_high=np.nan,
                            reference_cv_MAE=np.nan,mean_only_cv_MAE=np.nan,reference_cv_RMSE=np.nan,reference_cv_bias=np.nan,
                            reference_improves_mean=False,bootstrap_valid_replicates=0,predictors='')
                if analysis!='energy' and qa.suspect_sensor:
                    record['status']='sensor QA hold: '+qa.sensor_reason;results.append(record);continue
                if qa.meter_mapping_review:
                    record['status']='meter mapping QA hold: '+qa.meter_reason;results.append(record);continue
                if tr.date.nunique()<20 or record['reference_weeks']<4:
                    record['status']='insufficient reference days/weeks';results.append(record);continue
                if te.empty or (analysis=='energy' and winner is None):
                    record['status']='no evaluation data or validated weather specification';results.append(record);continue
                selected=[f for f in fields if tr[f].nunique()>1]
                record['predictors']=', '.join(selected)
                try:
                    fit=model.fit_reference(tr,selected,target)
                    scores, cv=model.temporal_cv(tr,selected,target)
                    benchmark,_=model.temporal_cv(tr,[],target)
                except (ValueError,np.linalg.LinAlgError) as exc:
                    record['status']='reference design/validation unavailable: '+str(exc);results.append(record);continue
                cv_tables.append(cv.assign(zone_id=label,analysis=analysis,variant=variant))
                for parameter,value in fit.params.items():
                    coefficients.append(dict(zone_id=label,analysis=analysis,variant=variant,parameter=parameter,value=value))
                record.update(reference_cv_MAE=scores['MAE'],reference_cv_RMSE=scores['RMSE'],reference_cv_bias=scores['bias'],
                              mean_only_cv_MAE=benchmark['MAE'],reference_improves_mean=bool(scores['MAE']<=benchmark['MAE']))
                te['prediction']=fit.predict(model.design(te,selected))
                te['actual']=te[target];te['residual']=te.actual-te.prediction
                support_fields=selected.copy()
                if analysis!='energy' and 'afternoon' not in support_fields: support_fields.append('afternoon')
                te['within_reference_support']=model.support_mask(tr,te,support_fields)
                if analysis=='energy':te['within_reference_support'] &= te.prediction.gt(0)
                te['analysis']=analysis
                predictions.append(te)
                supported=te[te.within_reference_support].copy()
                weeks=supported.date.dt.to_period('W-SUN').nunique()
                record.update(supported_rows=len(supported),supported_days=supported.date.nunique(),evaluation_weeks=weeks)
                reportable=supported.date.nunique()>=10 and weeks>=4
                record['reportable']=bool(reportable)
                if reportable:
                    w=model.weights_by_day(supported)
                    actual=float(np.average(supported.actual,weights=w));expected=float(np.average(supported.prediction,weights=w))
                    interval=model.block_bootstrap(tr,supported,selected,target,repetitions=repetitions)
                    record.update(observed_mean=actual,reference_expected_mean=expected,mean_residual=actual-expected,
                                  residual_pct=100*(actual-expected)/expected if expected>0 else np.nan,
                                  bootstrap_low=interval['low'],bootstrap_high=interval['high'],
                                  bootstrap_percent_low=interval['percent_low'],bootstrap_percent_high=interval['percent_high'],
                                  bootstrap_valid_replicates=interval['valid_replicates'])
                    record['lead_eligible']=bool(record['reference_improves_mean'] and interval['valid_replicates']>=.9*repetitions)
                    record['status']='supported descriptive comparison' if record['lead_eligible'] else 'supported; reference does not improve mean-only validation'
                else:
                    record['status']='insufficient supported evaluation days/weeks'
                results.append(record)
        print(f'{label}: model assessment complete',flush=True)
    output={'model_summary':pd.DataFrame(results),'predictions':pd.concat(predictions,ignore_index=True),
            'coefficients':pd.DataFrame(coefficients),'energy_candidates':pd.DataFrame(candidates),
            'cross_validation':pd.concat(cv_tables,ignore_index=True),'shared_cohort_checks':pd.DataFrame(checks),
            'cohort_counts':pd.DataFrame(counts)}
    for name,data in output.items():data.to_csv(output_dir/f'{name}.csv',index=False)
    return output


def benchmark_sensitivity(evidence, result, output_dir, repetitions=2000):
    """Compare a mean-only reference on each primary model's exact supported cohort.

    This diagnoses reliance on the weather/session formulation; it is not a
    replacement weather-adjusted estimate and never changes the selected model.
    """
    tables={'energy':evidence['daily_features'][evidence['daily_features'].eligible],
            'cooling':evidence['event_features'],'moisture':evidence['steady_on_features']}
    rows=[]
    for row in result['model_summary'].query('reportable').itertuples():
        data=tables[row.analysis]
        tr=data[(data.zone_id==row.zone_id)&(data.variant==row.variant)&(data.year==2018)]
        p=result['predictions']
        te=p[(p.zone_id==row.zone_id)&(p.variant==row.variant)&(p.analysis==row.analysis)&p.within_reference_support]
        actual=float(np.average(te[row.target],weights=model.weights_by_day(te)))
        expected=float(np.average(tr[row.target],weights=model.weights_by_day(tr)))
        interval=model.block_bootstrap(tr,te,[],row.target,repetitions=repetitions)
        rows.append(dict(zone_id=row.zone_id,analysis=row.analysis,variant=row.variant,
                         supported_days=te.date.nunique(),mean_only_residual=actual-expected,
                         mean_only_residual_pct=100*(actual-expected)/expected if expected>0 else np.nan,
                         bootstrap_low=interval['low'],bootstrap_high=interval['high'],
                         bootstrap_percent_low=interval['percent_low'],bootstrap_percent_high=interval['percent_high']))
    table=pd.DataFrame(rows)
    table.to_csv(Path(output_dir)/'benchmark_sensitivity.csv',index=False)
    return table


def inspection_shortlist(quality, summary, benchmark):
    """Exploratory triage, requiring consistency across both input versions.

    Nominal intervals across many zones are not multiplicity-adjusted tests.
    No validated engineering fault cutoff or composite score is invented.
    """
    rows=[]
    for qa in quality.itertuples():
        record=dict(zone_id=qa.zone_id,floor=qa.floor,zone=qa.zone,ac_meters=qa.ac_meters,
                    suspect_sensor=qa.suspect_sensor,meter_mapping_review=qa.meter_mapping_review,
                    sensor_reason=qa.sensor_reason,meter_reason=qa.meter_reason)
        signals={};descriptive={};available=0;single_version=[]
        for analysis in ['energy','cooling','moisture']:
            part=summary[(summary.zone_id==qa.zone_id)&(summary.analysis==analysis)].set_index('variant')
            assert set(part.index)==set(model.VARIANTS)
            valid=part.lead_eligible.all()
            positive=valid and part.bootstrap_low.gt(0).all()
            negative=valid and part.bootstrap_high.lt(0).all()
            signals[analysis]='positive' if positive else 'negative' if negative else 'unresolved'
            bench=benchmark[(benchmark.zone_id==qa.zone_id)&(benchmark.analysis==analysis)]
            bpositive=len(bench)==2 and bench.bootstrap_low.gt(0).all()
            bnegative=len(bench)==2 and bench.bootstrap_high.lt(0).all()
            descriptive[analysis]=('positive' if part.reportable.all() and part.bootstrap_low.gt(0).all() and bpositive
                                   else 'negative' if part.reportable.all() and part.bootstrap_high.lt(0).all() and bnegative
                                   else 'unresolved')
            if valid:available+=1
            if part.lead_eligible.sum()==1:single_version.append(analysis)
            for variant in model.VARIANTS:
                r=part.loc[variant]
                for name in ['mean_residual','residual_pct','supported_days','supported_rows','reference_days','reference_cv_MAE',
                             'bootstrap_low','bootstrap_high','bootstrap_percent_low','bootstrap_percent_high','lead_eligible','status']:
                    record[f'{analysis}_{variant}_{name}']=r[name]
            record[f'{analysis}_consistent_direction']=signals[analysis]
            record[f'{analysis}_benchmark_supported_direction']=descriptive[analysis]
        if qa.meter_mapping_review:
            category='Verify AC meter mapping'
            reason=qa.meter_reason
        elif qa.suspect_sensor:
            category='Verify environmental sensor'
            reason=qa.sensor_reason+'; energy assessed independently'
        elif signals['moisture']=='positive' or signals['cooling']=='negative':
            category='Inspect AC and operating conditions'
            reason='; '.join(x for yes,x in [(signals['moisture']=='positive','higher recorded absolute moisture'),
                                             (signals['cooling']=='negative','slower comparable cooling')] if yes)
        elif signals['energy']=='positive':
            category='Inspect energy and controls'
            reason='higher supported energy use in both input versions; efficiency/fault cause unconfirmed'
        elif descriptive['moisture']=='positive' or descriptive['cooling']=='negative':
            category='Inspect environment; validate reference'
            reason='adverse environmental departure persists in both versions and mean-only sensitivity; reference validation is weak'
        elif descriptive['energy']=='positive':
            category='Inspect energy change; validate reference'
            reason='higher energy persists in both versions and mean-only sensitivity; weather reference validation is weak'
        elif signals['energy']=='negative':
            category='Review operating change'
            reason='lower supported energy use in both input versions; check schedules/setpoints before interpreting performance'
        elif record['energy_with_fills_bootstrap_low']>0 and pd.isna(record['energy_without_fills_mean_residual']):
            category='Review fill-dependent energy lead'
            reason='higher energy in fills-allowed comparison; no supported observed-only comparison, so check reference availability before interpreting'
        elif available==0:
            category='Insufficient comparable evidence'
            reason='no metric passes coverage, support and reference-validation gates in both input versions'
        else:
            category='No consistent adverse departure'
            reason='no adverse direction supported by both versions; this does not certify equipment health'
        record.update(inspection_category=category,reason=reason,validated_metrics_in_both_versions=available,
                      validation_passes_only_one_version=', '.join(single_version))
        rows.append(record)
    return pd.DataFrame(rows)


def plot_evidence(evidence, summary, output_dir):
    """Static, exportable scientific figures with coverage and unavailable rows visible."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    output_dir=Path(output_dir)
    labels=evidence['zone_quality'].zone_id.tolist()
    q=evidence['zone_quality'].set_index('zone_id')
    fig,ax=plt.subplots(figsize=(9,8),layout='constrained')
    fields=[f'{v}_{year}_joint_coverage_pct' for v in model.VARIANTS for year in [2018,2019]]
    values=q.loc[labels,fields].to_numpy()
    im=ax.imshow(values,vmin=0,vmax=100,cmap='Blues',aspect='auto')
    ax.set_xticks(range(4),['2018\nfills allowed','2019\nfills allowed','2018\nobserved only','2019\nobserved only'])
    ax.set_yticks(range(len(labels)),labels)
    for y in range(len(labels)):
        for x in range(4):
            ax.text(x,y,f'{values[y,x]:.1f}%',ha='center',va='center',color='white' if values[y,x]>65 else '#17314c',fontsize=9)
    fig.colorbar(im,ax=ax,label='Valid joint AC / temperature / RH minutes (%)')
    ax.set_title('July–August input coverage across the 20 BQ2 zones',loc='left',fontsize=13,pad=15)
    fig.supxlabel('Coverage describes availability; sensor and meter QA holds are assessed separately.',fontsize=9)
    fig.savefig(output_dir/'input_coverage.png',dpi=180,bbox_inches='tight')
    plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(12,10),sharey=True)
    fig.subplots_adjust(left=.08,right=.99,top=.94,bottom=.18,wspace=.04)
    colors={'with_fills':'#27649c','without_fills':'#b06b21'}
    for ax,analysis,point,low,high,xlabel in [
        (axes[0],'energy','residual_pct','bootstrap_percent_low','bootstrap_percent_high','AC electricity departure (%)'),
        (axes[1],'moisture','mean_residual','bootstrap_low','bootstrap_high','Indoor humidity-ratio departure (g/kg dry air)')]:
        for j,label in enumerate(labels):
            part=summary[(summary.zone_id==label)&summary.analysis.eq(analysis)].set_index('variant')
            for variant,offset in [('with_fills',-.13),('without_fills',.13)]:
                r=part.loc[variant]
                if not r.reportable:continue
                color=colors[variant]
                # Hollow points retain evidence from references that fail the mean benchmark.
                ax.errorbar(r[point],j+offset,xerr=[[max(0,r[point]-r[low])],[max(0,r[high]-r[point])]],
                            fmt='o' if variant=='with_fills' else 's',color=color,markersize=5,capsize=3,
                            markerfacecolor=color if r.lead_eligible else 'white',linewidth=1)
        ax.axvline(0,color='#59636c',linestyle='--',linewidth=1)
        ax.set_yticks(range(len(labels)),labels)
        ax.set_ylim(len(labels)-.5,-.5)
        ax.grid(axis='y',alpha=.15)
        ax.set_axisbelow(True)
        ax.set_xlabel(xlabel,fontsize=10)
        ax.set_title('Daily energy' if analysis=='energy' else 'Recorded indoor moisture',loc='left')
    handles=[Line2D([],[],color=colors['with_fills'],marker='o',linestyle='',label='Fills allowed'),
             Line2D([],[],color=colors['without_fills'],marker='s',linestyle='',label='Observed only'),
             Line2D([],[],color='#59636c',marker='o',markerfacecolor='white',linestyle='',label='Hollow: reference fails mean-only validation')]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.07),ncol=3,fontsize=9)
    fig.suptitle('2019 departures from each zone’s 2018 reference, July–August',fontsize=14)
    fig.text(.5,.02,'Nominal conditional 95% week-bootstrap intervals, without multiplicity adjustment.\nBlank rows lack an eligible comparison.',
             ha='center',va='bottom',fontsize=9)
    fig.savefig(output_dir/'zone_comparison.png',dpi=180,bbox_inches='tight')
    plt.close(fig)
    return ['input_coverage.png','zone_comparison.png']

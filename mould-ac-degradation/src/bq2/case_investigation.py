"""Focused operating-state diagnostics for three screened BQ2 zones.

Read-only source analysis. Contributions are accounting, not causal effects.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from . import zone_screen as screen
from . import reference_models as model

CASES={3:4,5:4,7:2}
OUTCOMES=['ac_kW','temp_C','rh_pct','indoor_w_gkg','plug_kW','peer_temp_C','peer_w_gkg']


def build_case_tables(root,weather,helpers,output_dir):
    root,output_dir=Path(root),Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    inputs=[root/'data-cleaning/outputs/analytics/zone_hourly.csv',
            root/'mould-ac-degradation/outputs/bq2-zone-screen/zone_quality.csv',
            root/'mould-ac-degradation/outputs/bq2-zone-screen/predictions.csv',
            root/'mould-ac-degradation/outputs/bq2-zone-screen/model_summary.csv',
            root/'baseline/data/bangkok_era5_hourly_2018-2019.csv',
            root/'mould-ac-degradation/bq2_utils.ipynb']
    day_info=pd.read_csv(inputs[0],parse_dates=['Date'])
    quality=pd.read_csv(inputs[1]).set_index('zone_id')
    weather=helpers['add_outdoor_psychrometrics'](weather)
    scope=model.scoped(screen.PERIOD)
    frames_out={'daily':[],'hourly':[],'events':[],'sensor_checks':[],'sensor_scenarios':[]}
    for floor,zone in CASES.items():
        label=f'F{floor}-Z{zone}'
        frames={}
        peers=[z for z in [1,2,4,5] if z!=zone and (floor,z)!=(5,1)]
        for kind,folder in [('raw','data'),('clean','data-cleaning/outputs/clean')]:
            parts=[]
            for year in [2018,2019]:
                path=root/folder/f'{year}Floor{floor}.csv';inputs.append(path)
                header=pd.read_csv(path,nrows=0).columns;spec=screen.column_spec(header,zone)
                cols=spec['ac']+[spec['temp'],spec['rh'],spec['plug']]
                cols+= [f'z{z}_S1({unit})' for z in peers for unit in ['degC','RH%']]
                data=pd.read_csv(path,usecols=['Date']+cols)
                fmt='%d/%m/%y %H:%M' if data.Date.str.contains('/').any() else '%Y-%m-%d %H:%M:%S'
                dates=pd.to_datetime(data.pop('Date'),format=fmt,errors='raise')
                assert not dates.duplicated().any() and dates.is_monotonic_increasing
                data.index=pd.DatetimeIndex(dates,name='Date');parts.append(data)
            frames[kind]=pd.concat(parts).reindex(screen.PERIOD).where(pd.Series(scope,index=screen.PERIOD),axis=0)
        observed=frames['raw'].where(frames['raw'].eq(frames['clean']))
        raw=frames['raw'];clean=frames['clean']
        threshold=float(quality.loc[label,'frozen_threshold_kW'])
        computed=helpers['ac_on_threshold'](observed[spec['ac']].sum(axis=1,min_count=len(spec['ac'])).loc['2018-07-01':'2018-08-31'])
        assert abs(computed-threshold)<1e-10
        day_type=day_info.query('floor == @floor and zone == @zone').set_index('Date').day_type
        day_type=day_type.groupby(day_type.index.normalize()).first()
        for fields,stream in [([spec['temp']],'temperature'),([spec['rh']],'RH'),([spec['temp'],spec['rh']],'paired')]:
            max_constant=screen.flatline_minutes(raw,fields)
            for c in fields[:1]:
                v=raw[c];delta=v.diff().abs().where(v.notna()&v.shift().notna())
                frames_out['sensor_checks'].append(dict(zone_id=label,stream=stream,max_constant_minutes=max_constant,
                    largest_minute_change=delta.max(),p999_minute_change=delta.quantile(.999),
                    largest_change_time=str(delta.idxmax())))
        for variant,frame in [('with_fills',clean),('without_fills',observed)]:
            ac=frame[spec['ac']].sum(axis=1,min_count=len(spec['ac']))
            masks=screen.valid_masks(frame,spec)
            on=masks.ac & ac.gt(threshold);off=masks.ac & ac.le(threshold)
            t,r,plug=frame[spec['temp']],frame[spec['rh']],frame[spec['plug']]
            w=helpers['humidity_ratio_gkg'](t,r)
            d=pd.DataFrame(index=frame.resample('D').size().index)
            complete=masks.energy.resample('D').sum().eq(1440)
            d['ac_kWh']=ac.resample('D').sum(min_count=1440)/60
            d['on_hours']=on.resample('D').sum()/60
            d['on_kWh']=ac.where(on,0).resample('D').sum()/60
            d['off_kWh']=ac.where(off,0).resample('D').sum()/60
            d['on_mean_kW']=d.on_kWh/d.on_hours
            d['plug_kWh']=plug.resample('D').sum(min_count=1440)/60
            clock=frame.index.hour+frame.index.minute/60
            interior=((clock>=8)&(clock<11))|((clock>=13.25)&(clock<16.25))
            d['interior_below_on_hours']=(off & interior).resample('D').sum()/60
            d['eligible']=complete & (d.index.normalize().map(day_type)=='working day') & model.scoped(d.index)
            d=d[d.eligible].copy();d['date']=d.index;d['year']=d.index.year
            d['variant'],d['zone_id']=variant,label
            assert np.allclose(d.ac_kWh,d.on_kWh+d.off_kWh,atol=1e-9)
            frames_out['daily'].append(d.reset_index(drop=True))
            h=pd.DataFrame({'ac_kW':ac.resample('h').mean(),'temp_C':t.resample('h').mean(),
                            'rh_pct':r.resample('h').mean(),'indoor_w_gkg':w.resample('h').mean(),
                            'plug_kW':plug.resample('h').mean(),'on_fraction':on.resample('h').mean()}).join(weather)
            full=masks.joint.resample('h').sum().eq(60) & plug.notna().resample('h').sum().eq(60)
            h['complete']=full
            h['working']=(h.index.normalize().map(day_type)=='working day')
            h['off_run_hours']=off.groupby((~off).cumsum()).cumsum().resample('h').last()/60
            near_zero=masks.ac & ac.le(.1)
            h['near_zero_run_hours']=near_zero.groupby((~near_zero).cumsum()).cumsum().resample('h').last()/60
            steady=on.rolling(120,min_periods=120).sum().eq(120).resample('h').last()
            night=off.rolling(120,min_periods=120).sum().eq(120).resample('h').last()
            h['state']=np.select([steady & h.index.hour.isin([9,10,14,15]),night & h.index.hour.isin([2,3,4,5])],
                                 ['steady_on','night_off'],default='other')
            peer_t=[];peer_w=[]
            for peer in peers:
                pt,pr=frame[f'z{peer}_S1(degC)'],frame[f'z{peer}_S1(RH%)']
                valid=pt.between(15,40)&pr.between(0,100)
                enough=valid.resample('h').sum().eq(60)
                peer_t.append(pt.resample('h').mean().where(enough))
                peer_w.append(helpers['humidity_ratio_gkg'](pt,pr).resample('h').mean().where(enough))
            tt=pd.concat(peer_t,axis=1);ww=pd.concat(peer_w,axis=1)
            h['peer_temp_C']=tt.median(axis=1).where(tt.notna().sum(axis=1)>=2)
            h['peer_w_gkg']=ww.median(axis=1).where(ww.notna().sum(axis=1)>=2)
            h=h[model.scoped(h.index)].copy()
            h['time'],h['date'],h['year'],h['hour']=h.index,h.index.normalize(),h.index.year,h.index.hour
            h['variant'],h['zone_id']=variant,label
            frames_out['hourly'].append(h.reset_index(drop=True))
            ev=model.strict_events(ac.where(masks.ac),threshold)
            ev=ev[ev.time.dt.month.isin([7,8]) & ev.time.dt.normalize().map(day_type).eq('working day')].copy()
            ev['clock_hour']=ev.time.dt.hour+ev.time.dt.minute/60
            ev['session']=np.select([ev.clock_hour.between(6,10.999),ev.clock_hour.between(11,14.999),
                                     ev.clock_hour.between(15,19.999)],['morning','lunch','evening'],default='other')
            ev['zone_id'],ev['variant'],ev['year']=label,variant,ev.time.dt.year
            frames_out['events'].append(ev)
            if label=='F7-Z2':
                # Exact minute-derived sensitivity, including opposing year-specific nominal design errors.
                for rh_error,t_error,name in [(0,0,'as_recorded'),(-2,-.4,'nominal_low'),(2,.4,'nominal_high')]:
                    corrected=helpers['humidity_ratio_gkg'](t+t_error,r+rh_error).resample('h').mean()
                    frames_out['sensor_scenarios'].append(pd.DataFrame({'time':h.time,'date':h.date,'year':h.year,
                        'variant':variant,'scenario':name,'indoor_w_gkg':corrected.reindex(h.index).to_numpy()}))
                for correction in [2,4,6,8,10]:
                    corrected=helpers['humidity_ratio_gkg'](t,r-correction).resample('h').mean()
                    frames_out['sensor_scenarios'].append(pd.DataFrame({'time':h.time,'date':h.date,'year':h.year,
                        'variant':variant,'scenario':f'RH_minus_{correction}pp','indoor_w_gkg':corrected.reindex(h.index).to_numpy()}))
        print(f'{label}: case inputs and operating-state features built',flush=True)
    result={k:(pd.DataFrame(v) if k == "sensor_checks" else pd.concat(v,ignore_index=True)) for k,v in frames_out.items()}
    for name,table in result.items():table.to_csv(output_dir/f'{name}.csv',index=False)
    manifest=[dict(path=str(p.relative_to(root)),sha256=screen.digest(p),bytes=p.stat().st_size) for p in inputs]
    (output_dir/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return result


def energy_decomposition(daily,predictions,output_dir):
    rows=[]
    for (zone,variant),group in daily.groupby(['zone_id','variant']):
        tr=group[group.year.eq(2018)]
        test_times=predictions[(predictions.zone_id==zone)&(predictions.variant==variant)&
                               predictions.analysis.eq('energy')&predictions.within_reference_support].time
        te=group[group.date.isin(test_times)]
        assert len(tr)>=20 and len(te)>=10
        def context(g):
            return dict(E=g.ac_kWh.mean(),H=g.on_hours.mean(),P=g.on_kWh.sum()/g.on_hours.sum(),
                        off=g.off_kWh.mean(),plug=g.plug_kWh.mean())
        a,b=context(tr),context(te)
        runtime=(b['H']-a['H'])*(b['P']+a['P'])/2
        power=(b['P']-a['P'])*(b['H']+a['H'])/2
        off=b['off']-a['off'];delta=b['E']-a['E']
        assert np.isclose(runtime+power+off,delta,atol=1e-9)
        rows.append(dict(zone_id=zone,variant=variant,reference_days=len(tr),evaluation_days=len(te),
                         energy_2018=a['E'],energy_2019=b['E'],energy_change_kWh=delta,
                         raw_energy_change_pct=100*delta/a['E'],on_hours_2018=a['H'],on_hours_2019=b['H'],
                         on_power_2018=a['P'],on_power_2019=b['P'],runtime_contribution_kWh=runtime,
                         power_contribution_kWh=power,off_contribution_kWh=off,
                         power_share_of_change_pct=100*power/delta,plug_2018=a['plug'],plug_2019=b['plug'],
                         median_on_hours_2018=tr.on_hours.median(),median_on_hours_2019=te.on_hours.median(),
                         days_over_9on_hours_2018=int(tr.on_hours.gt(9).sum()),days_over_9on_hours_2019=int(te.on_hours.gt(9).sum()),
                         interior_below_on_hours_2018=tr.interior_below_on_hours.mean(),
                         interior_below_on_hours_2019=te.interior_below_on_hours.mean()))
    table=pd.DataFrame(rows);table.to_csv(Path(output_dir)/'energy_decomposition.csv',index=False)
    return table


def match_matrix(train,test,scale=1.0):
    """Exact clock/state, outdoor calipers, and a 2018-defined plug caliper."""
    plug_caliper=max(.1,.2*float(train.plug_kW.median()))*scale
    matrix=(test.hour.to_numpy()[:,None]==train.hour.to_numpy()[None,:])
    for field,caliper in [('outdoor_temp_C',1.0*scale),('outdoor_w_gkg',1.0*scale),('plug_kW',plug_caliper)]:
        matrix &= np.abs(test[field].to_numpy()[:,None]-train[field].to_numpy()[None,:])<=caliper+1e-10
    return matrix,plug_caliper


def state_population(hourly):
    ordinary=hourly[hourly.complete & hourly.working & hourly.state.ne('other')].copy()
    # Overlapping control cohort, not an additional independent population.
    control=hourly[hourly.complete & hourly.near_zero_run_hours.ge(24) & hourly.hour.isin([2,3,4,5])].copy()
    control['state']='long_off'
    return pd.concat([ordinary,control],ignore_index=True)


def matched_states(hourly,output_dir):
    """Descriptive state comparisons; no new causal or inferential intervals."""
    summaries,details,balance=[],[],[]
    eligible=state_population(hourly)
    metrics=['ac_kW','temp_C','rh_pct','indoor_w_gkg','plug_kW']
    for (zone,variant,state),group in eligible.groupby(['zone_id','variant','state']):
        tr=group[group.year.eq(2018)].sort_values('time').reset_index(drop=True)
        te=group[group.year.eq(2019)].sort_values('time').reset_index(drop=True)
        for name,scale in [('primary',1.0),('tighter',.5),('looser',1.5)]:
            m,plug_caliper=match_matrix(tr,te,scale)
            selected=m.sum(axis=1)>=3
            selected_test=te[selected].copy().reset_index(drop=True);m=m[selected]
            reference_used=tr.loc[m.any(axis=0)]
            days=selected_test.date.nunique()
            passes=days>=10 and reference_used.date.nunique()>=10 and selected_test.date.dt.to_period('W-SUN').nunique()>=4 and reference_used.date.dt.to_period('W-SUN').nunique()>=4
            base=dict(zone_id=zone,variant=variant,state=state,specification=name,eligible_2018_hours=len(tr),
                      eligible_2019_hours=len(te),matched_hours=len(selected_test),matched_days=days,
                      reference_days=reference_used.date.nunique(),reportable=bool(passes),plug_caliper_kW=plug_caliper)
            if len(selected_test):
                w=model.weights_by_day(selected_test)
                pred=m.astype(float)@tr[metrics].to_numpy()/m.sum(axis=1)[:,None]
                for j,metric in enumerate(metrics):
                    observed=np.average(selected_test[metric],weights=w);reference=np.average(pred[:,j],weights=w)
                    summaries.append(dict(**base,metric=metric,observed_mean=observed,reference_mean=reference,
                                          mean_change=observed-reference if passes else np.nan))
                for field in ['outdoor_temp_C','outdoor_w_gkg','plug_kW']:
                    ref=m.astype(float)@tr[field].to_numpy()/m.sum(axis=1)
                    balance.append(dict(**base,field=field,mean_target_minus_reference=float(np.average(selected_test[field]-ref,weights=w))))
                if name=='primary':
                    detail=selected_test[['zone_id','variant','state','time','date','year','hour']].copy()
                    detail['candidate_reference_hours']=m.sum(axis=1)
                    for j,metric in enumerate(metrics):
                        detail[f'actual_{metric}']=selected_test[metric].to_numpy()
                        detail[f'reference_{metric}']=pred[:,j]
                        detail[f'change_{metric}']=selected_test[metric].to_numpy()-pred[:,j]
                    detail['reportable']=passes;details.append(detail)
            else:
                for metric in metrics:summaries.append(dict(**base,metric=metric,observed_mean=np.nan,reference_mean=np.nan,mean_change=np.nan))
    result={'matched_states':pd.DataFrame(summaries),'matched_details':pd.concat(details,ignore_index=True),
            'matching_balance':pd.DataFrame(balance)}
    for name,table in result.items():table.to_csv(Path(output_dir)/f'{name}.csv',index=False)
    return result


def sensor_sensitivity(hourly,scenarios,output_dir):
    rows=[]
    eligible=state_population(hourly)
    eligible=eligible[eligible.zone_id.eq('F7-Z2')]
    for (variant,state),group in eligible.groupby(['variant','state']):
        tr=group[group.year.eq(2018)].sort_values('time').reset_index(drop=True)
        te=group[group.year.eq(2019)].sort_values('time').reset_index(drop=True)
        m,_=match_matrix(tr,te)
        keep=m.sum(axis=1)>=3;te=te[keep].copy().reset_index(drop=True);m=m[keep]
        if not len(te):continue
        w=model.weights_by_day(te)
        def values(frame,scenario):
            series=scenarios[(scenarios.variant==variant)&(scenarios.scenario==scenario)].set_index('time').indoor_w_gkg
            return series.reindex(frame.time).to_numpy()
        for label,ref_name,test_name in [('as_recorded','as_recorded','as_recorded'),
                  ('opposing_nominal_errors_min','nominal_high','nominal_low'),
                  ('opposing_nominal_errors_max','nominal_low','nominal_high'),
                  ('same_nominal_low_both_years','nominal_low','nominal_low')]+[
                      (f'2019_RH_minus_{x}pp','as_recorded',f'RH_minus_{x}pp') for x in [2,4,6,8,10]]:
            reference=m.astype(float)@values(tr,ref_name)/m.sum(axis=1)
            delta=float(np.average(values(te,test_name)-reference,weights=w))
            rows.append(dict(zone_id='F7-Z2',variant=variant,state=state,scenario=label,
                             matched_hours=len(te),matched_days=te.date.nunique(),moisture_change_gkg=delta))
    table=pd.DataFrame(rows);table.to_csv(Path(output_dir)/'sensor_bias_sensitivity.csv',index=False)
    return table


def profiles_and_persistence(data,matching,output_dir):
    h=data['hourly'];h=h[h.complete & h.working].copy()
    profiles=h.groupby(['zone_id','variant','year','hour']).agg(hours=('time','size'),days=('date','nunique'),
        ac_kW=('ac_kW','mean'),on_fraction=('on_fraction','mean'),temp_C=('temp_C','mean'),
        rh_pct=('rh_pct','mean'),indoor_w_gkg=('indoor_w_gkg','mean')).reset_index()
    ev=data['events'];schedule=ev.groupby(['zone_id','variant','year','session','event']).clock_hour.agg(['size','median','min','max']).reset_index()
    dt=matching['matched_details'].copy();dt['month']=dt.time.dt.month
    month=[]
    for (zone,variant,state,mo),g in dt.groupby(['zone_id','variant','state','month']):
        w=model.weights_by_day(g)
        r=dict(zone_id=zone,variant=variant,state=state,month=mo,matched_days=g.date.nunique(),matched_hours=len(g))
        for metric in ['ac_kW','temp_C','rh_pct','indoor_w_gkg']:
            r[f'change_{metric}']=np.average(g[f'change_{metric}'],weights=w)
        month.append(r)
    peer=h[h.state.ne('other') & h.peer_temp_C.notna() & h.peer_w_gkg.notna()].copy()
    peer['relative_temp_C']=peer.temp_C-peer.peer_temp_C;peer['relative_w_gkg']=peer.indoor_w_gkg-peer.peer_w_gkg
    peer_table=peer.groupby(['zone_id','variant','year','state']).agg(hours=('time','size'),
        relative_temp_C=('relative_temp_C','mean'),relative_w_gkg=('relative_w_gkg','mean')).reset_index()
    tables={'clock_hour_profiles':profiles,'event_schedule':schedule,'monthly_matched_changes':pd.DataFrame(month),
            'peer_context':peer_table}
    for name,t in tables.items():t.to_csv(Path(output_dir)/f'{name}.csv',index=False)
    return tables


def state_contrasts(details,output_dir):
    """Same-day state contrasts cancel a uniform additive T or RH offset.

    These remain descriptive associations; day/night thermal loads differ.
    """
    rows=[]
    for (zone,variant),group in details.groupby(['zone_id','variant']):
        for minimum in [1,2]:
            night=group[group.state.eq('night_off')]
            on=group[group.state.eq('steady_on')]
            n=night.groupby('date').size();o=on.groupby('date').size()
            dates=n[n>=minimum].index.intersection(o[o>=minimum].index)
            for metric in ['temp_C','rh_pct','indoor_w_gkg']:
                a=night.groupby('date')[f'change_{metric}'].mean().reindex(dates)
                b=on.groupby('date')[f'change_{metric}'].mean().reindex(dates)
                reportable=len(dates)>=10 and pd.DatetimeIndex(dates).to_period('W-SUN').nunique()>=4
                rows.append(dict(zone_id=zone,variant=variant,minimum_hours_each_state=minimum,
                    paired_days=len(dates),metric=metric,reportable=bool(reportable),
                    change_in_on_minus_night_contrast=(b-a).mean() if reportable else np.nan,
                    median_change_in_contrast=(b-a).median() if reportable else np.nan))
    table=pd.DataFrame(rows);table.to_csv(Path(output_dir)/'state_contrasts.csv',index=False)
    return table


def plot_cases(data,decomposition,output_dir):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    p=Path(output_dir)
    profiles=pd.read_csv(p/'clock_hour_profiles.csv')
    fig,axes=plt.subplots(3,3,figsize=(12,8),sharex=True,sharey='row')
    fig.subplots_adjust(left=.07,right=.99,top=.91,bottom=.14,wspace=.06,hspace=.14)
    metrics=[('ac_kW','AC power (kW)'),('temp_C','Ceiling temperature (°C)'),('indoor_w_gkg','Humidity ratio (g/kg)')]
    for col,zone in enumerate(['F3-Z4','F5-Z4','F7-Z2']):
        for row,(field,ylabel) in enumerate(metrics):
            ax=axes[row,col]
            for variant,style in [('with_fills','-'),('without_fills','--')]:
                for year,color in [(2018,'#27649c'),(2019,'#b06b21')]:
                    d=profiles[(profiles.zone_id==zone)&(profiles.variant==variant)&(profiles.year==year)]
                    ax.plot(d.hour,d[field],color=color,linestyle=style,linewidth=1.5)
            if col==0:ax.set_ylabel(ylabel)
            if row==0:ax.set_title(zone,loc='left',fontweight='bold')
            if row==2:ax.set_xlabel('Clock hour')
            ax.set_xticks([0,6,12,18,23]);ax.grid(alpha=.16);ax.set_xlim(0,23)
    legend=[Line2D([],[],color='#27649c',label='2018 reference'),Line2D([],[],color='#b06b21',label='2019 evaluation'),
            Line2D([],[],color='#58636e',linestyle='-',label='Fills allowed'),Line2D([],[],color='#58636e',linestyle='--',label='Observed only')]
    fig.legend(handles=legend,loc='lower center',bbox_to_anchor=(.5,.045),ncol=4,fontsize=9)
    fig.suptitle('July–August working-day profiles: electrical operation and sensor readings',fontsize=13)
    fig.text(.5,.015,'Full joint hours only; descriptive cohorts differ by year and input version. Ceiling sensors do not measure delivered cooling.',ha='center',fontsize=9)
    fig.savefig(p/'operating_profiles.png',dpi=180,bbox_inches='tight');plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,5))
    fig.subplots_adjust(left=.09,right=.99,top=.88,bottom=.23)
    colors=['#5b8cbd','#bd7e35','#737f8c']
    names=['Runtime contribution','On-power contribution','Below-threshold energy contribution']
    fields=['runtime_contribution_kWh','power_contribution_kWh','off_contribution_kWh']
    labels=[]
    for x,row in enumerate(decomposition.itertuples()):
        pos,neg=0,0
        for field,color in zip(fields,colors):
            value=getattr(row,field);bottom=pos if value>=0 else neg
            ax.bar(x,value,bottom=bottom,color=color,width=.7)
            if value>=0:pos+=value
            else:neg+=value
        net=row.energy_change_kWh
        ax.plot(x,net,marker='D',color='#202c36',markersize=4,zorder=5)
        ax.annotate(f'{net:+.1f}',(x,net),xytext=(0,7 if net>=0 else -13),textcoords='offset points',
                    ha='center',fontsize=10,bbox=dict(facecolor='white',alpha=.85,edgecolor='none',pad=.5))
        labels.append(row.zone_id+'\n'+('Fills' if row.variant=='with_fills' else 'Observed'))
    ax.set_xticks(range(len(labels)),labels);ax.axhline(0,color='#39434c',linewidth=1)
    ax.set_ylabel('Change in mean daily AC electricity (kWh)');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    ax.margins(y=.15)
    ax.set_title('Accounting for the observed energy change',loc='left',fontsize=13)
    from matplotlib.patches import Patch
    handles=[Patch(facecolor=c,label=n) for c,n in zip(colors,names)]
    handles.append(Line2D([],[],marker='D',linestyle='',color='#202c36',label='Net change'))
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.065),ncol=4,fontsize=8)
    fig.text(.5,.015,'2018 reference days versus the screen’s supported 2019 days. Symmetric accounting decomposition; these are not causal contributions.',ha='center',fontsize=8.5)
    fig.savefig(p/'energy_contributions.png',dpi=180,bbox_inches='tight');plt.close(fig)
    return ['operating_profiles.png','energy_contributions.png']


def conclusions(output_dir):
    """Reporting language deliberately separates recorded facts from mechanism."""
    table=pd.DataFrame([
        dict(zone_id='F3-Z4',assessment='Operating pattern changed; sensor comparability unresolved',
             confident_observation='Recorded energy increased. More above-threshold time and higher on-power both contribute; low-power time inside shared business-hour windows fell.',
             plausible_explanation='More continuous operation or changed control/load conditions; an environmental sensor baseline or ambient-state change also remains plausible.',
             sensor_evidence='Cooler readings persist during regional-weather/clock-matched periods with at least 24 hours near-zero AC power. Flatline screening does not verify calibration.',
             degradation_status='Not established. Higher energy alone does not measure delivered cooling or efficiency.',
             next_check='Verify sensor continuity and meter/control settings; inspect within-session control changes before assigning a degradation cause.',
             reportable_wording='F3-Z4 shows a change in metered AC operation, with increased on-time and on-power. Environmental year comparisons remain sensitive to an unresolved baseline shift, so AC degradation cannot be confirmed.'),
        dict(zone_id='F5-Z4',assessment='Higher electrical loading; control/load or sensor changes require verification',
             confident_observation='On-power rose from about 15.1 to 20.1 kW on the comparison cohorts while runtime stayed near 7.45 hours/day. On-power accounts for about 99% of the unadjusted energy difference.',
             plausible_explanation='A changed operating/load regime is consistent with the electrical readings; thermostat, equipment or meter changes are unverified.',
             sensor_evidence='Cooler readings also persist in the long near-zero-power control. Additional on-state cooling association is descriptive, not measured cooling output.',
             degradation_status='Not established. The weather reference is weak; neither inefficiency nor verified overcooling can be reported.',
             next_check='Check metering configuration, control/setpoint and equipment-change records, and sensor calibration/placement.',
             reportable_wording='F5-Z4 used more electricity mainly through higher power during operation rather than longer runtime. This warrants control/load and metering checks; the data do not establish AC degradation or actual overcooling.'),
        dict(zone_id='F7-Z2',assessment='Possible AC-associated performance/control issue; physical cause unresolved',
             confident_observation='Recorded steady-on moisture is about 1.15 g/kg higher under matched conditions with little on-power change. The on-versus-night temperature/moisture association also changed and the moisture lead persists in both months.',
             plausible_explanation='Control changes, ventilation or internal moisture, sensor changes and reduced AC dehumidification remain competing explanations.',
             sensor_evidence='Published nominal design-error scenarios can erase the absolute matched moisture increase; this is a sensitivity scenario, not evidence of actual sensor bias. Constant additive T/RH offsets do not explain all observed state contrasts.',
             degradation_status='Possible diagnostic lead only. No confirmed dehumidification loss, mechanical fault or progressive failure trend.',
             next_check='Verify calibration and sensor continuity, then inspect controls, ventilation/moisture loads and AC maintenance/coil/condensate performance using site records.',
             reportable_wording='F7-Z2 shows higher recorded moisture during sustained AC operation and a weaker day-versus-night cooling association. The pattern warrants joint sensor, operating-condition and AC checks; physical degradation remains unconfirmed.')])
    table['observation_confidence']='High for the recorded quantities and stated cohorts'
    table['cause_confidence']='Limited; causal mechanism is not identifiable from these records'
    table.to_csv(Path(output_dir)/'case_conclusions.csv',index=False)
    return table

from ortools.sat.python import cp_model
import sys
import csv
import queue
from threading import Event
from check_values import check_values_csv

mini_all_wards = ['W4M','W9','MDR','IMW','W4F']
super_all_wards = ['W4M','W9','MDR','IMW','ART','PSYCH','W4F']

def main(
        d_num_gps, #total number of gps
        d_num_days, #total number of days
        d_first_day_index, #first day index starting from monday as 0
        d_freedays_after_duty, #freedays to have after each duty
        d_is_first_day_psych, #is the first day psych or not (boolean)
        d_max_min, #maximum minute to run the search 
        d_prev_duty_shift=[], #dict values for all basic wards 
        d_prev_duty_shift_new = None, #dict values for all basic wards 
        d_holiday_dates = [], #date of holidays
        msg_queue = queue.Queue(), #to be used to get messages on background when used with GUI (like tkinter)
        stop_event = Event(), #to be used to stop search from background when used with GUI (like tkinter)
        end_event = Event(), #to indicate the search has been completed with result
):
    #create a model
    model = cp_model.CpModel()

    #callback when the function finds any solution
    class Solution_Callback(cp_model.CpSolverSolutionCallback):
        def __init__(self,solver:cp_model.CpSolver,stop_event: Event):
            super().__init__()
            self.solver = solver
            self.stop_event = stop_event
        
        def on_solution_callback(self):
            msg_queue.put(f'Obj: {self.ObjectiveValue()}\t'+f'diff in hr:{self.value(max_hr)-self.value(min_hr)}')
            if self.stop_event.is_set():
                self.solver.stop_search()
    #basic constants
    days_of_week=['mon','tue','wed','thr','fri','sat','sun']
    all_wards = mini_all_wards
    all_possible_wards = all_wards.copy()
    mul_hr_scale=10
    hrs_per_week = {
        days_of_week[0]: int(16), days_of_week[1]: int(16), days_of_week[2]: int(16),days_of_week[3]: int(16),
        days_of_week[4]: int(17),
        days_of_week[5]: int(24),days_of_week[6]: int(24)
    }
    multiplied_hrs_per_week = {
        days_of_week[0]: int(16*1.5*mul_hr_scale), days_of_week[1]: int(16*1.5*mul_hr_scale), days_of_week[2]: int(16*1.5*mul_hr_scale), days_of_week[3]: int(16*1.5*mul_hr_scale),
        days_of_week[4]: int(17*1.5*mul_hr_scale),
        days_of_week[5]: int(24*2*mul_hr_scale),days_of_week[6]: int(24*2*mul_hr_scale)
    }
    ART_hrs = 8
    holiday_hrs = 24
    hol_hr_mul = int(holiday_hrs*2.5*mul_hr_scale)
    ART_hr_mul = int(ART_hrs*2*mul_hr_scale)
    ART_hol_hr_mul = int(ART_hrs*2.5*mul_hr_scale)
    duty_types = ['actual','signed']
    #Basic setups
    #previous duty
    if not d_prev_duty_shift_new:
        prev_duty_shift = d_prev_duty_shift_new
    elif d_prev_duty_shift:
        prev_duty_shift={
            0:{
                (all_wards[0]): d_prev_duty_shift[0][all_wards[0]], #w4
                (all_wards[1]): d_prev_duty_shift[0][all_wards[1]], #w9
                (all_wards[2]): d_prev_duty_shift[0][all_wards[2]], #mdr
                (all_wards[3]): d_prev_duty_shift[0][all_wards[3]], #imw
                # (all_wards[4],duty_types[1]): d_prev_duty_shift[0][all_wards[4]][1], #imw
            },
            1:{
                (all_wards[0]): d_prev_duty_shift[0][all_wards[0]], #w4
                (all_wards[1]): d_prev_duty_shift[0][all_wards[1]], #w9
                (all_wards[2]): d_prev_duty_shift[0][all_wards[2]], #mdr
                (all_wards[3]): d_prev_duty_shift[0][all_wards[3]], #imw
                # (all_wards[4],duty_types[1]): d_prev_duty_shift[0][all_wards[4]][1], #imw
            },
            2:{
                (all_wards[0]): d_prev_duty_shift[0][all_wards[0]], #w4
                (all_wards[1]): d_prev_duty_shift[0][all_wards[1]], #w9
                (all_wards[2]): d_prev_duty_shift[0][all_wards[2]], #mdr
                (all_wards[3]): d_prev_duty_shift[0][all_wards[3]], #imw
                # (all_wards[4],duty_types[1]): d_prev_duty_shift[0][all_wards[4]][1], #imw
            }
        }
    else:
        prev_duty_shift={}
    #coping values of arguments
    num_gps = d_num_gps
    num_days = d_num_days + len(prev_duty_shift)
    first_day_index = d_first_day_index
    freedays_after_duty = d_freedays_after_duty
    is_first_day_psych = d_is_first_day_psych
    holiday_date_index = list(map(lambda x: x+len(prev_duty_shift)-1,d_holiday_dates))
    
    all_gps = range(num_gps)
    all_days = range(num_days)
    # not_eff_gps = []
    not_eff_gps = []

    duty_shifts={}

    def get_day_of_week(d,first_day_index=first_day_index):
        change_k = 7 - len(prev_duty_shift) if len(prev_duty_shift)<=7 else 7 - (len(prev_duty_shift)%7)
        return int(d+first_day_index+change_k)%(len(days_of_week)) if (d+first_day_index+change_k)>=len(days_of_week) else int(d+first_day_index+change_k)
    
    def is_skippable(d,w,t):
        return False
        dow = get_day_of_week(d)
        if (not (d in holiday_date_index)) and dow != 5 and dow != 6 and w in [all_wards[0],all_wards[1]] and t==duty_types[1]:
            return True
        if w in [all_wards[3]] and (dow==5 or dow==6 or d in holiday_date_index):
            return True
        return False
    
    def is_psych_not(d,first_d, is_first_day_true):
        if d<first_d: return False
        fde = True if first_d//2==0 else False
        even_day_true_logic = (fde and is_first_day_true or (not fde and not  is_first_day_true))
        if(d%2==0):
            #even logic
            if(even_day_true_logic):
                return True
            else:
                return False
        elif(d%2==1):
            #odd logic
            if(not even_day_true_logic):
                return True
            else:
                return False

    def get_d_for_index_at_week(required_day_index:int,weekend_index:int):
        return (weekend_index*7)+required_day_index-first_day_index+len(prev_duty_shift)
    def get_week_for_d(d:int):
        return (d+first_day_index)//7
    # def map_weekend_with_d():
        # pass

    #create boolean variable for all basic wards for gp duties
    for gp in all_gps:
        for d in all_days:
            for w in all_wards:
                duty_shifts[(gp,d,w)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}")
                if duty_shifts[(gp,d,w)].Index() in range(0,1) or duty_shifts[(gp,d,w)].Index() in [6755,4221,5334]:
                    print(gp, d,w,duty_shifts[(gp,d,w)].Index())
                # for t in duty_types:
                #     if is_skippable(d,w,t):
                #         continue
                #     duty_shifts[(gp,d,w,t)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}")
                #     if duty_shifts[(gp,d,w,t)].Index() in range(504,519) or duty_shifts[(gp,d,w,t)].Index() in [3586]:
                #         print(gp, d,w,duty_shifts[(gp,d,w,t)].Index())
    #create boolean variable for ART ward
    all_possible_wards.append('ART')
    for d in all_days:
        dow = get_day_of_week(d)
        if dow == 5 or dow == 6 or d in holiday_date_index:
            w = 'ART'
            for gp in all_gps:
                duty_shifts[(gp,d,w)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}")
                if duty_shifts[(gp,d,w)].Index() in [6755,4221,5334]:
                    print(gp, d,w,duty_shifts[(gp,d,w)].Index())
    #create boolean variable for psych ward
    all_possible_wards.append('PSYCH')
    for d in range(len(prev_duty_shift),num_days):
        if is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
            w='PSYCH'
            # t=duty_types[1]
            for gp in all_gps:
                duty_shifts[(gp,d,w)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}")
                if duty_shifts[(gp,d,w)].Index() in [6755,4221,5334]:
                        print(gp, d,w,duty_shifts[(gp,d,w)].Index())
                # print(gp, d,'p ',duty_shifts[(gp,d,w,t)].Index())
    
    #add rules (constraints)
    #rule 1: each duty needs to be covered by exactly one gp
    for d in all_days:
        for w in all_wards:
            model.add_exactly_one(duty_shifts[(gp,d,w)] for gp in all_gps)
        if d>=len(prev_duty_shift) and is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
            model.add_exactly_one([duty_shifts[(gp,d,'PSYCH')] for gp in all_gps])
    #rule 2:one gp can at most have one duty per day
    for gp in all_gps:
        for d in all_days:
            dow = get_day_of_week(d)
            basic_wards = [duty_shifts[(gp,d,w)] for w in all_wards]
            art_ward=[]
            psych_ward=[]
            if dow==5 or dow==6 or d in holiday_date_index:
                art_ward.append(duty_shifts[(gp,d,'ART')])
            if d>=len(prev_duty_shift) and is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
                psych_ward.append(duty_shifts[(gp,d,'PSYCH')])
            model.add_at_most_one(basic_wards + art_ward + psych_ward)
    #rule 3: each gp should cover IMW before repeating the cycle
    #becomes hard rule if holidays or entry or skip is multiple; caution
    # duty_cycle_day = num_gps // len(duty_types)
    # duty_for_num_days = num_days//duty_cycle_day
    # for gp in all_gps:
    #     if duty_for_num_days!=0:
    #         w = all_wards[4]
    #         for d in all_days:
    #             for cc in range(duty_for_num_days):
    #                 i=cc*duty_cycle_day+d if cc*duty_cycle_day+d<num_days else num_days
    #                 j=(cc+1)*duty_cycle_day+d if (cc+1)*duty_cycle_day+d<num_days else num_days
    #                 model.add_at_most_one(duty_shifts[(gp,dd,w,t)] for t in duty_types for dd in range(i,j))
    # #rule 4: each gp should one have one countable (actual entered) based on free day after duty variable
    countable_wards = all_wards.copy()
    countable_wards.remove('MDR')
    def force_free_after_duty(d,freedays_after_duty,gp):
        i = d
        j = d+freedays_after_duty+1 if d+freedays_after_duty+1<num_days else num_days
        gen_all_assigned = [duty_shifts[(gp,dd,ww)] for dd in range(i,j) for ww in countable_wards]
        # gen_imw_signed = [duty_shifts[(gp,dd,all_wards[4],duty_types[1])] for dd in range(i,j)]
        model.add_at_most_one(gen_all_assigned)
    # day_sick_leaved = list(map(lambda d:d+len(prev_duty_shift)-1,[i for i in range(1,14)])) #on leave days
    # day_sick_leaved = [] #on leave days
    for gp in all_gps:
        for d in all_days:
            force_free_after_duty(d,freedays_after_duty,gp)
            # for w in countable_wards:
                # if is_skippable(d,w,t):
                #     continue
                    #with leave
                # if d in day_sick_leaved:
                #     force_free_after_duty(d,1,gp)
                #     continue
                    #without leave
    #rule 5: use previous shift to prevent overlaps
    for dd, dict1 in prev_duty_shift.items():
        for (ww), old_gp in dict1.items():
            model.add(duty_shifts[(old_gp, dd, ww)] == 1)

    #rule 6: Adding ART (other dependent ward)
    for d in all_days:
        if d<len(prev_duty_shift):
            # pass
            continue
        w = 'ART'
        ART_possible_ward = all_wards.copy()
        ART_possible_ward.remove('MDR')
        ART_possible_ward.remove('IMW')
        dow = get_day_of_week(d)
        if dow == 5 or dow == 6 or d in holiday_date_index:
            model.add_exactly_one(duty_shifts[(gp,d,w)] for gp in all_gps)
            for gp in all_gps:
                model.add_at_most_one(duty_shifts[(gp,d,w)])
            if d-1<0:
                continue
            for gp in all_gps:
                one_day_back = d-1
                prev_day_duty_gp_values = [duty_shifts[(gp,one_day_back,ww)] for ww in ART_possible_ward]
                # curr_day_duty_gp_values = [duty_shifts[(gp,d,w,tt)] for tt in duty_types] #want to use for both actual and signed ART from prev duty
                curr_day_duty_gp_values = [duty_shifts[(gp,d,w)]] #want to use just actual not signed for one day back rule
                pddgv = model.new_bool_var(f"prev_gp{gp}_d{d}_w{w}")
                cddgv = model.new_bool_var(f"curr_gp{gp}_d{d}_w{w}")
                model.add_bool_or(prev_day_duty_gp_values).only_enforce_if(pddgv)
                model.add_bool_or(curr_day_duty_gp_values).only_enforce_if(cddgv)
                model.add(sum(curr_day_duty_gp_values)==0).only_enforce_if(pddgv.Not())
                # print(gp,' ',pddgv.Index())
    #optimization calculation for each gp
    #one gp should have at least one duty on the weekends (signed or actual)
    #infeasible with low numbner
    # def once_in_every_weekend_if_feasible(gp:int):
    #     max_weekend_index= (first_day_index+num_days-1)//7
    #     for w in range(max_weekend_index+1):
    #         sat_d_in_w = get_d_for_index_at_week(5,w)
    #         sun_d_in_w = get_d_for_index_at_week(6,w)
    #         # if sat_d_in_w >= num_days or sun_d_in_w >= num_days or sat_d_in_w<0 or sun_d_in_w<0:
    #         #     break
    #         # print(sat_d_in_w,sun_d_in_w)
    #         #if both weekends exist in num_days and not out of bound
    #         if sat_d_in_w < num_days and sat_d_in_w>=len(prev_duty_shift) and sun_d_in_w < num_days  and sun_d_in_w>=len(prev_duty_shift) :
    #             if sun_d_in_w in range(13) and gp in not_eff_gps:
    #                 return
    #             basic_wards_values = [duty_shifts[(gp,d,w,t)] for d in [sat_d_in_w,sun_d_in_w] for w in all_wards for t in duty_types if not is_skippable(d,w,t)]
    #             psych_wards_values = [duty_shifts[(gp,d,'PSYCH',duty_types[1])] for d in [sat_d_in_w,sun_d_in_w] if is_psych_not(d,len(prev_duty_shift),is_first_day_psych)]
                
    #             model.add_at_least_one(basic_wards_values+psych_wards_values)    
    #total gp hour
    cal_gp_hrs={}
    max_hr = model.new_int_var(0,24*num_days,f"max_gp_hrs")
    min_hr = model.new_int_var(0,24*num_days,f"min_gp_hrs")
    avg_hr = model.new_int_var(0,24*num_days,f"avg_gp_hrs")
    total_hr = model.new_int_var(0,24*num_days*num_gps,f"total_gp_hrs")
    model.add(max_hr>=min_hr)
    #effective gp hour
    eff_gp_hrs={}
    max_eff_hr = model.new_int_var(0,24*num_days,f"max_gp_eff_hrs")
    min_eff_hr = model.new_int_var(0,24*num_days,f"min_gp_eff_hrs")
    model.add(max_eff_hr>=min_eff_hr)
    #multiplied mon hour
    mon_gp_hrs={}
    max_mon_hr = model.new_int_var(0,3*24*num_days*mul_hr_scale,f"max_gp_mon_hrs")
    min_mon_hr = model.new_int_var(0,3*24*num_days*mul_hr_scale,f"min_gp_mon_hrs")
    model.add(max_mon_hr>=min_mon_hr)
    #effective signed gp hour
    eff_signed_gp_hrs={}
    max_eff_signed_hr = model.new_int_var(0,24*num_days,f"max_gp_eff_signed_hrs")
    min_eff_signed_hr = model.new_int_var(0,24*num_days,f"min_gp_eff_signed_hrs")
    model.add(max_eff_signed_hr>=min_eff_signed_hr)
    #total imw entry (assigned)
    cal_gp_imw_num = {}
    max_imw_num = model.new_int_var(0,num_days,f"max_gp_imw_num")
    min_imw_num = model.new_int_var(0,num_days,f"min_gp_imw_num")
    model.add(max_imw_num>=min_imw_num)
    #total signed hours
    cal_gp_signed_hrs = {}
    max_signed_hrs = model.new_int_var(0,24*num_days,f"max_gp_signed_hrs")
    min_signed_hrs = model.new_int_var(0,24*num_days,f"min_gp_signed_hrs")
    model.add(max_signed_hrs>=min_signed_hrs)
    #total weekend hours
    cal_gp_weekend_hol_hrs = {}
    max_weekend_hol_hrs = model.new_int_var(0,24*num_days,f"max_gp_weekend_hol_hrs")
    min_weekend_hol_hrs = model.new_int_var(0,24*num_days,f"min_gp_weekend_hol_hrs")
    model.add(max_weekend_hol_hrs>=min_weekend_hol_hrs)
    #total weekend nums
    cal_gp_weekend_hol_num = {}
    max_weekend_hol_num = model.new_int_var(0,(num_days//7)-1+len(holiday_date_index),f"max_gp_weekend_hol_num")
    min_weekend_hol_num = model.new_int_var(0,(num_days//7)-1+len(holiday_date_index),f"min_gp_weekend_hol_num")
    model.add(max_weekend_hol_num>=min_weekend_hol_num)
    #total imw weekend entry (assigned)
    cal_gp_imw_weekend_num = {}
    max_imw_weekend_num = model.new_int_var(0,(num_days//7)+1,f"max_gp_imw_weekend_num")
    min_imw_weekend_num = model.new_int_var(0,(num_days//7)+1,f"min_gp_imw_weekend_num")
    model.add(max_imw_weekend_num>=min_imw_weekend_num)
    for gp in all_gps:
        #calculate hours for each gp
        cal_gp_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_hrs({gp})")
        basic_wards_hrs_values = [duty_shifts[(gp,d,w)]*holiday_hrs if d in holiday_date_index else duty_shifts[(gp,d,w)]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) for w in all_wards]
        psych_wards_hrs_values = [duty_shifts[(gp,d,'PSYCH')]*holiday_hrs if d in holiday_date_index else duty_shifts[(gp,d,'PSYCH')]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) if is_psych_not(d,len(prev_duty_shift),is_first_day_psych)]
        ART_hrs_values = [duty_shifts[(gp,d,'ART')]*ART_hrs for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index]
        model.add(cal_gp_hrs[gp]==sum(basic_wards_hrs_values + ART_hrs_values + psych_wards_hrs_values))
        model.add(cal_gp_hrs[gp]<=max_hr)
        model.add(cal_gp_hrs[gp]>=min_hr)
        if (not (gp in not_eff_gps)) or not_eff_gps.__len__==0:
            eff_gp_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_eff_hrs({gp})")
            model.add(eff_gp_hrs[gp]==cal_gp_hrs[gp])
            model.add(eff_gp_hrs[gp]<=max_eff_hr)
            model.add(eff_gp_hrs[gp]>=min_eff_hr)
        #calculate mon hours for each gp
        mon_gp_hrs[gp] = model.new_int_var(0,3*24*num_days*mul_hr_scale,f"gp_hrs({gp})")
        basic_wards_mon_hrs_values = [duty_shifts[(gp,d,w)]*hol_hr_mul if d in holiday_date_index else duty_shifts[(gp,d,w)]*multiplied_hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) for w in all_wards]
        psych_wards_mon_hrs_values = [duty_shifts[(gp,d,'PSYCH')]*hol_hr_mul if d in holiday_date_index else duty_shifts[(gp,d,'PSYCH')]*multiplied_hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) if is_psych_not(d,len(prev_duty_shift),is_first_day_psych)]
        ART_mon_hrs_values = [duty_shifts[(gp,d,'ART')]*ART_hol_hr_mul if d in holiday_date_index else duty_shifts[(gp,d,'ART')]*ART_hr_mul for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index]
        model.add(mon_gp_hrs[gp]==sum(basic_wards_mon_hrs_values + ART_mon_hrs_values + psych_wards_mon_hrs_values))
        # model.add(mon_gp_hrs[gp]>sum(basic_wards_mon_hrs_values + ART_mon_hrs_values + psych_wards_mon_hrs_values)-1)
        # model.add(mon_gp_hrs[gp]<=sum(basic_wards_mon_hrs_values + ART_mon_hrs_values + psych_wards_mon_hrs_values))
        model.add(mon_gp_hrs[gp]<=max_mon_hr)
        model.add(mon_gp_hrs[gp]>=min_mon_hr)
        #calculate signed hours for each gp
        cal_gp_signed_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_signed_hrs({gp})")
        # basic_wards_signed_hrs_values = [duty_shifts[(gp,d,w)]*holiday_hrs if d in holiday_date_index else duty_shifts[(gp,d,w)]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) for w in all_wards if (not is_skippable(d,w,duty_types[1])) and w!=all_wards[4]]
        MDR_as_signed_hr = [duty_shifts[(gp,d,all_wards[2])]*holiday_hrs if d in holiday_date_index else duty_shifts[(gp,d,all_wards[2])]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days)]
        # ART_signed_hrs_values = [
        #     duty_shifts[(gp,d,'ART',t)]*ART_hrs if get_day_of_week(d) == 6 else duty_shifts[(gp,d,'ART',duty_types[1])]*ART_hrs 
        #     for t in duty_types 
        #     for d in range(len(prev_duty_shift),num_days) 
        #     if get_day_of_week(d) == 5 or get_day_of_week(d) ==6] #if sat actual is considered as entry
        ART_as_signed_hrs = [duty_shifts[(gp,d,'ART')]*ART_hrs for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index]
        # psych_wards_hrs_values = [duty_shifts[(gp,d,'PSYCH',duty_types[1])]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) if is_psych_not(d,len(prev_duty_shift),is_first_day_psych)]
        model.add(cal_gp_signed_hrs[gp]==sum(
            # basic_wards_signed_hrs_values 
            MDR_as_signed_hr
            +ART_as_signed_hrs
            +psych_wards_hrs_values
            ))
        model.add(cal_gp_signed_hrs[gp]<=max_signed_hrs)
        model.add(cal_gp_signed_hrs[gp]>=min_signed_hrs)
        if (not (gp in not_eff_gps)) or not_eff_gps.__len__==0:
            eff_signed_gp_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_eff_signed_hrs({gp})")
            model.add(eff_signed_gp_hrs[gp]==cal_gp_signed_hrs[gp])
            model.add(eff_signed_gp_hrs[gp]<=max_eff_signed_hr)
            model.add(eff_signed_gp_hrs[gp]>=min_eff_signed_hr)
        #calculate how many imw entry
        cal_gp_imw_num[gp] = model.new_int_var(0,num_days,f"gp_imw_num({gp})")
        imw_num_by_each_gp = [duty_shifts[(gp,d,all_wards[3])] for d in range(len(prev_duty_shift),num_days)]
        model.add(cal_gp_imw_num[gp]==sum(imw_num_by_each_gp))
        model.add(cal_gp_imw_num[gp]<=max_imw_num)
        model.add(cal_gp_imw_num[gp]>=min_imw_num)
        #calculate how many weekend entry
        # once_in_every_weekend_if_feasible(gp)
        cal_gp_weekend_hol_num[gp] = model.new_int_var(0,num_days,f"gp_weekend_num({gp})")
        weekend_all_assigned = [duty_shifts[(gp,d,ww)] for ww in countable_wards for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index]
        # weekend_imw_signed = [duty_shifts[(gp,d,all_wards[4],duty_types[1])]  for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index]
        model.add(cal_gp_weekend_hol_num[gp]==sum(weekend_all_assigned))
        model.add(cal_gp_weekend_hol_num[gp]<=max_weekend_hol_num)
        model.add(cal_gp_weekend_hol_num[gp]>=min_weekend_hol_num)
        #calculate how much weekend hrs
        cal_gp_weekend_hol_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_weekend_hrs({gp})")
        weekend_basic_hrs_values = [duty_shifts[(gp,d,ww)]*hrs_per_week[days_of_week[get_day_of_week(d)]] for ww in countable_wards for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index]
        weekend_psych_hrs_values = [duty_shifts[(gp,d,'PSYCH')]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) if is_psych_not(d,len(prev_duty_shift),is_first_day_psych) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index]
        model.add(cal_gp_weekend_hol_hrs[gp]==sum(weekend_basic_hrs_values + weekend_psych_hrs_values))
        model.add(cal_gp_weekend_hol_hrs[gp]<=max_weekend_hol_hrs)
        model.add(cal_gp_weekend_hol_hrs[gp]>=min_weekend_hol_hrs)
        #calculate how many weekend imw entry
        cal_gp_imw_weekend_num[gp] = model.new_int_var(0,num_days,f"gp_imw_weekend_num({gp})")
        weekend_imw_num = [duty_shifts[(gp,d,all_wards[3])] for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
        model.add(cal_gp_imw_weekend_num[gp]==sum(weekend_imw_num))
        model.add(cal_gp_imw_weekend_num[gp]<=max_imw_weekend_num)
        model.add(cal_gp_imw_weekend_num[gp]>=min_imw_weekend_num)
    #calculate average gp hours
    model.add(total_hr==sum([cal_gp_hrs[gp] for gp in all_gps ]))
    # model.add(avg_hr*num_gps == sum([cal_gp_hrs[gp] for gp in all_gps]))
    # model.add(total_hr == avg_hr * num_gps)
    model.add_division_equality(avg_hr,total_hr,num_gps)

    #personalized preferrences
    #can't be on schedule
    def skip_duty_all(sgp:int,sds:list[int],use_sds_direct=False):
        if not use_sds_direct:
            sds = list(map(lambda d:d+len(prev_duty_shift)-1,sds))
        skip_basic_wards_values = [duty_shifts[(sgp,d,w)] for d in sds for w in all_wards]
        skip_psych_wards_values = [
            duty_shifts[(sgp,d,'PSYCH')] 
            for d in sds if is_psych_not(d,len(prev_duty_shift),is_first_day_psych)]
        skip_ART_values = [
            duty_shifts[(sgp,d,'ART')] 
            for d in sds 
            if get_day_of_week(d) == 5 or get_day_of_week(d) ==6 or d in holiday_date_index
        ]
        model.add(sum(skip_basic_wards_values+skip_psych_wards_values+skip_ART_values)==0)
    #can't_be_on_duty function
    def skip_duty(sgp:int,sds:list[int],sws=countable_wards,use_sds_direct=False):
        if not use_sds_direct:
            sds = list(map(lambda d:d+len(prev_duty_shift)-1,sds))
        sgp_values = [
            duty_shifts[(sgp,d,w)] 
            for d in sds for w in sws 
            # if (w!='PSYCH' and not is_skippable(d,w,t)) or (w=='PSYCH' and is_psych_not(d,len(prev_duty_shift),is_first_day_psych))
        ]
        model.add(sum(sgp_values)==0)
    #must be on duty function
    def entry_duty(sgp:int,sds:list[int],sws=countable_wards):
        sds = list(map(lambda d:d+len(prev_duty_shift)-1,sds))
        for d in sds:
            # sgp_values = [duty_shifts[(sgp,d,w,t)] if w==all_wards[4] else duty_shifts[(sgp,d,w,duty_types[0])] for w in sws for t in duty_types if not is_skippable(d,w,t) and (w==all_wards[4] or (w!=all_wards[4]and t==duty_types[0]))] #works but hard to read
            sgp_values_basic = [duty_shifts[(sgp,d,w)] for w in sws]
            # sgp_values_imw = [duty_shifts[(sgp,d,all_wards[4])]]
            model.add(sum(sgp_values_basic)==1)
            # model.add_exactly_one(sgp_values)
    #GP_9 will not be working on sundays
    # agp9_sun_ds = [d for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d)==6]
    # skip_duty(9,agp9_sun_ds,use_sds_direct=True)
    # for d in all_days:
    #     dow = get_day_of_week(d)
    #     if dow == 6:
    #         agp = 9
    #         agp_values = [duty_shifts[(agp,d,w,t)] if w==all_wards[4] else duty_shifts[(agp,d,w,duty_types[0])] for w in countable_wards for t in duty_types]
    #         model.add(sum(agp_values)==0) 
    #GP-0: can't be on duty on tuesday; on saturday = be in intermediate
    # for d in range(len(prev_duty_shift),num_days):
    #     agp = 0
    #     dow= get_day_of_week(d)
    #     #tuesday rule
    #     if dow==1:
    #         skip_duty(agp,[d],use_sds_direct=True)
    #         # agp_values = [duty_shifts[(agp,d,w,t)] if w==all_wards[4] else duty_shifts[(agp,d,w,duty_types[0])] for w in countable_wards for t in duty_types if not is_skippable(d,w,t)]   
    #         # model.add(sum(agp_values)==0)
    #     #saturday intermediate rule
    #     if dow == 5:
    #         skip_duty(agp,[d],[w for w in countable_wards if w !=all_wards[4]],use_sds_direct=True)
    #         # agp_values = [duty_shifts[(agp,d,w,duty_types[0])] for w in countable_wards if w!=all_wards[4]]
    #         # model.add(sum(agp_values)==0
    #make gp 2 in same duty with gp 1 as much as possible
    count_gp_2_assigned = model.new_int_var(0,num_days,f"gp_2_assigned_count")
    assigned_values_gp_2 = [duty_shifts[(2,d,w)] for d in range(len(prev_duty_shift),num_days) for w in countable_wards]
    model.add(count_gp_2_assigned==sum(assigned_values_gp_2))
    list_gp_2_1_together=[]
    for d in range(len(prev_duty_shift),num_days):
        has_gp2_enter = model.new_bool_var(f"has_gp2_on{d}")
        has_gp1_enter = model.new_bool_var(f"has_gp1_on{d}")
        model.add_max_equality(has_gp2_enter,[duty_shifts[(2,d,w)] for w in countable_wards ])
        model.add_max_equality(has_gp1_enter,[duty_shifts[(1,d,w)] for w in countable_wards ])
        mark_d = model.new_bool_var(f"mark_{d}_{2}_{1}")
        model.add_bool_and([has_gp1_enter,has_gp2_enter]).only_enforce_if(mark_d)
        model.add_bool_or([has_gp1_enter.Not(),has_gp2_enter.Not()]).only_enforce_if(mark_d.Not())
        list_gp_2_1_together.append(mark_d)
    count_gp_2_1_together = model.new_int_var(0,num_days,f"count_gp_2_1_together")
    model.add(count_gp_2_1_together==sum(list_gp_2_1_together))
    #make two gps not on same day as much as possible (for post duty)
    def count_them_if_together(i,gpx,gpy, ws = countable_wards,weekend_inc = True):
        list_gp_x_y_together=[]
        for d in range(len(prev_duty_shift),num_days):
            if not(weekend_inc) and (get_day_of_week(d) in [5,6]):
                continue
            has_gpx_enter = model.new_bool_var(f"has_{gpx}_on{d}{i}")
            has_gpy_enter = model.new_bool_var(f"has_{gpy}_on{d}{i}")
            model.add_max_equality(has_gpx_enter,[duty_shifts[(gpx,d,w)] for w in ws])
            model.add_max_equality(has_gpy_enter,[duty_shifts[(gpy,d,w)] for w in ws])
            mark_d = model.new_bool_var(f"mark_{d}_{gpx}_{gpy}_{i}")
            # if i == 1245:
            #     print(has_gpy_enter.Index()," y",i,d)
            #     print(has_gpx_enter.Index()," x",i,d)
            #     print(mark_d.Index()," md",i,d)
            model.add_bool_and([has_gpy_enter,has_gpx_enter]).only_enforce_if(mark_d)
            model.add_bool_or([has_gpy_enter.Not(),has_gpx_enter.Not()]).only_enforce_if(mark_d.Not())
            list_gp_x_y_together.append(mark_d)
        count_gp_x_y_together = model.new_int_var(0,num_days,f"count_gp_{gpx}_{gpy}_together{i}")
        model.add(count_gp_x_y_together==sum(list_gp_x_y_together))
        return count_gp_x_y_together
    to_be_apart = [ #day time same shift
        (8,12), #w4
        (1,4),#MDR
        (2,5),#ART
        (6,7),#IMW
        (0,11),#w9
    ]
    list_count_together_to_be_appart = []
    for i,agps in enumerate(to_be_apart):
        list_count_together_to_be_appart.append(count_them_if_together(i,agps[0],agps[1]))
    # #sick gp not be assigned to w9 (no intern)
    # assigned_values_gp_8_at_w9 = [duty_shifts[(8,d,all_wards[2],duty_types[0])] for d in range(len(prev_duty_shift),num_days)]
    # model.add(sum(assigned_values_gp_8_at_w9)==0)
    # #Intern duty related to cover sick gp 
    # intern_duty_shifts ={}
    # intern_duty_wards=['W4','IMW']
    # intern_duty_counter = 0
    # intern_duty_sets = {
    #     intern_duty_wards[0]:[],
    #     intern_duty_wards[1]:[],
    #     'leave':[]
    # }
    # for d in range(len(prev_duty_shift),num_days):
    #     for iww in intern_duty_wards:
    #         intern_duty_shifts[(d,iww)]= model.new_bool_var(f"shift_intern_d{d}_w{iww}")
    #     model.add_at_most_one([intern_duty_shifts[(d,iww)] for iww in intern_duty_wards])
    #     #does she have a duty
    #     if d%3==2 :
    #         intern_duty_counter+=1
    #         model.add(intern_duty_shifts[(d,intern_duty_wards[intern_duty_counter%2])]==1)
    #         if intern_duty_counter%2 == 0:
    #             #w4 entry; no IMW entry
    #             # model.add(sum([duty_shifts[(8,d,all_wards[4],t)] for t in duty_types])==0)
    #             intern_duty_sets[intern_duty_wards[0]].append(d)
    #             # skip_duty(8,[d-len(prev_duty_shift)+1],[all_wards[4]])
    #         else:
    #             intern_duty_sets[intern_duty_wards[1]].append(d)
    #         #     #IMW
    #         #     skip_duty(8,[d-len(prev_duty_shift)+1],[all_wards[0],all_wards[1]])
    #         #     # model.add(sum([duty_shifts[(8,d,w,duty_types[0])] for w in [all_wards[0],all_wards[1]] for t in duty_types if not is_skippable(d,w,t)])==0)
    #     else:
    #         #no duty
    #         intern_duty_sets['leave'].append(d)
    #         for iww in intern_duty_wards: 
    #             model.add(intern_duty_shifts[(d,iww)]==0)
    #         # skip_duty(8,[d-len(prev_duty_shift)+1])
    #         # model.add(sum([duty_shifts[(8,d,w,t)] if w == all_wards[4] else duty_shifts[(8,d,w,duty_types[0])] for w in countable_wards for t in duty_types if not is_skippable(d,w,t)])==0)
    # # skip_duty(8,[wrid-len(prev_duty_shift)+1 for wrid in intern_duty_sets[intern_duty_wards[0]]],[all_wards[2],all_wards[4]])
    # skip_duty(8,[wrid-len(prev_duty_shift)+1 for wrid in intern_duty_sets['leave']])
    # #sick gp working together with intern gp_8
    # count_gp_8_assigned = model.new_int_var(0,num_days,f"gp_8_assigned_count")
    # assigned_values_gp_8 = [duty_shifts[(8,d,w,t)] if w == all_wards[4] else duty_shifts[(8,d,w,duty_types[0])] for d in range(len(prev_duty_shift),num_days) for w in countable_wards for t in duty_types if not is_skippable(d,w,t)]
    # model.add(count_gp_8_assigned==sum(assigned_values_gp_8))
    # list_gp_8_intern_together=[]
    # for d in range(len(prev_duty_shift),num_days):
    #     for w in countable_wards:
    #         if w == all_wards[2]:
    #             continue
    #         has_intern_enter = model.new_bool_var(f"has_intern_on{d}_{w}")
    #         has_gp_8_enter = model.new_bool_var(f"has_gp_8_on{d}_{w}")
    #         if w in [all_wards[0],all_wards[1]]:
    #             model.add_max_equality(has_intern_enter,[intern_duty_shifts[(d,intern_duty_wards[0])] ])
    #             # model.add(sum([duty_shifts[(8,d,w,duty_types[0])] for t in duty_types if not is_skippable(d,w,t)])==0).only_enforce_if(intern_duty_shifts[(d,intern_duty_wards[0])].Not())
    #         elif w == all_wards[4]:
    #             # iww = intern_duty_wards[1]
    #             model.add_max_equality(has_intern_enter,[intern_duty_shifts[(d,intern_duty_wards[1])] ])
    #             # model.add(sum([duty_shifts[(8,d,w,t)] for t in duty_types])==0).only_enforce_if(intern_duty_shifts[(d,intern_duty_wards[1])].Not())
    #         else:
    #             continue
    #         model.add_max_equality(has_gp_8_enter,[duty_shifts[(8,d,w,t)] if w == all_wards[4] else duty_shifts[(8,d,w,duty_types[0])] for t in duty_types if not is_skippable(d,w,t)])
    #         mark_d = model.new_bool_var(f"mark_{d}_{w}_8_intern")
    #         model.add_bool_and([has_gp_8_enter,has_intern_enter]).only_enforce_if(mark_d)
    #         model.add_bool_or([has_gp_8_enter.Not(),has_intern_enter.Not()]).only_enforce_if(mark_d.Not())
    #         list_gp_8_intern_together.append(mark_d)
    #         # model.add(sum([duty_shifts[(8,d,w,t)] if w == all_wards[4] else duty_shifts[(8,d,w,duty_types[0])] for t in duty_types if not is_skippable(d,w,t)])==0).only_enforce_if(has_intern_enter.Not())
    #     count_gp_8_intern_together = model.new_int_var(0,num_days,f"count_gp_8_intern_together")
    #     model.add(count_gp_8_intern_together==sum(list_gp_8_intern_together))
    # model.add(cal_gp_hrs[8]==min_hr)
    # model.add(cal_gp_signed_hrs[8]==min_signed_hrs)
    # #make gp 2 take a leave for 11 days
    # skip_duty_all(2,[i for i in range(1,12)])
    # skip_duty(2,[29])
    # skip_duty(2,[i for i in range(1,12)])
    # model.add(cal_gp_hrs[2]==min_hr)
    # model.add(max_hr-cal_gp_hrs[2]<=64) #hard rule
    #GP_1 personal skip
    # skip_duty(1,[4])
    #GP_6 personal skip
    # skip_duty(6,[28,29])
    #GP_11 personal skip
    # skip_duty(11,[28,29])
    # model.add(cal_gp_weekend_hol_num[11]==min_weekend_hol_num)
    #Must enter for 29
    # entry_duty(4,[29])
    # entry_duty(5,[29])
    # entry_duty(7,[29])
    # entry_duty(13,[29])
    # entry_duty(1,[29])
    #GP_10 and GP_11 together in IMW
    # count_10_11_imw_together = count_them_if_together(1245,10,11,[all_wards[4]],False)
    # model.add(count_10_11_imw_together>=1)
    #compensating old mishaps
    ## making disadvantaged gps have high hours
    # model.add(cal_gp_hrs[5]==max_hr)
    # model.add(cal_gp_hrs[8]>=max_hr-2)
    # model.add(cal_gp_hrs[12]>=max_hr-2)
    ## OR recalculating the lost or add hours over the average to compensate
    # def mishap_gen (value_list,gp,avg_hr,constant):
    #     comp_gp_hr_constant = model.new_int_var(num_days*24*-100,num_days*24*100,f"comp_gp_hr_{gp}")
    #     # model.add(comp_gp_hr_constant==4*(cal_gp_hrs[gp]-(avg_hr+constant)))
    #     model.add_abs_equality(comp_gp_hr_constant,cal_gp_hrs[gp]-(avg_hr+constant))
    #     value_list.append(comp_gp_hr_constant)
    # comp_gp_value_list = []
    # #mishap_gen(comp_gp_value_list,0,avg_hr,-10) #prev advantageous 
    # #mishap_gen(comp_gp_value_list,4,avg_hr,-25) #prev advantageous
    # mishap_gen(comp_gp_value_list,5,avg_hr,22) #prev disadvantageous
    # #mishap_gen(comp_gp_value_list,6,avg_hr,61) #prev disadvantageous
    # #mishap_gen(comp_gp_value_list,7,avg_hr,-1) #prev advantageous
    # mishap_gen(comp_gp_value_list,8,avg_hr,22) #prev disadvantageous
    # #mishap_gen(comp_gp_value_list,1,avg_hr,-4) #prev advantageous
    # mishap_gen(comp_gp_value_list,12,avg_hr,25) #prev disadvantageous
    ##OR only compensating for prev disadvantegous 
    # for gp in all_gps:
    #     list_comp_gps = [0,4,5,8,1,12]
    #     if gp not in list_comp_gps:
    #         mishap_gen(comp_gp_value_list,gp,avg_hr,0)
    # comp_gp_value_list.append(cal_gp_hrs[0]-(avg_hr-39.4))
    # comp_gp_value_list.append(cal_gp_hrs[4]-(avg_hr-44.4))
    # comp_gp_value_list.append(cal_gp_hrs[5]-(avg_hr+51.6))
    # comp_gp_value_list.append(cal_gp_hrs[6]-(avg_hr+60.6))
    # comp_gp_value_list.append(cal_gp_hrs[7]-(avg_hr-1.4))
    # comp_gp_value_list.append(cal_gp_hrs[8]-(avg_hr-35.6))
    # comp_gp_value_list.append(cal_gp_hrs[9]-(avg_hr-12.4))
    # comp_gp_value_list.append(cal_gp_hrs[9]-(avg_hr+18.6))
    # comp_gp_value_list.append(cal_gp_hrs[9]-(avg_hr-18.4))
    ## optimization functions for compensating old mishaps
    # fairness_minimizer = model.new_int_var(0,24*num_days*num_gps*100,f"fairness_minimizer")
    # model.add(fairness_minimizer==4*(max_hr-min_hr)+2*(max_weekend_hol_num-min_weekend_hol_num)+4*(max_signed_hrs-min_signed_hrs))
    # compensation_minimizer = model.new_int_var(num_days*24*-100,num_days*24*100,f"compensation_minimizer")
    # model.add(compensation_minimizer==2*(cal_gp_hrs[5]-cal_gp_hrs[8])+3*(cal_gp_hrs[5]-cal_gp_hrs[12]))
    ## Final minimize model if compensating old mishaps occured
    # model.minimize(4*fairness_minimizer + compensation_minimizer)
    # model.minimize(fairness_minimizer+(count_gp_2_assigned-count_gp_2_1_together)) #add gp_2 and gp_1 togther benefit
    #hard rules to make it better if possible
    # model.add(max_weekend_hol_num-min_weekend_hol_num<=1)
    # model.add(count_gp_8_assigned-count_gp_8_intern_together==0) #do this only after feasiblity check
    # model.add(max_weekend_hol_hrs-min_weekend_hol_hrs==0) #do this only after feasiblity check
    # model.add(max_eff_hr-min_eff_hr<=8) #do this only after feasiblity check
    # model.add(max_eff_signed_hr-min_eff_signed_hr<=17) #do this only after feasiblity check
    model.add(max_hr<=212)
    model.minimize(
        2*(max_hr-min_hr) #total hr
        +2*(max_signed_hrs-min_signed_hrs) #signed hrs
        +8*(max_mon_hr-min_mon_hr) #mon hrs
        +2*(max_eff_hr-min_eff_hr) # effective total hr 
        +2*(max_eff_signed_hr-min_eff_signed_hr) #effective signed hrs
        +2*(max_weekend_hol_hrs-min_weekend_hol_hrs) #all hrs in weekend
        +4*(max_weekend_hol_num-min_weekend_hol_num) #entry in weekend
        +4*(max_imw_weekend_num-min_imw_weekend_num) #entry in imw at weekend
        +4*(max_imw_num-min_imw_num) #entry in imw
        #+2*(cal_gp_hrs[5]-cal_gp_hrs[8])+3*(cal_gp_hrs[5]-cal_gp_hrs[12])
        # +4*(count_gp_2_assigned-count_gp_2_1_together)
        +8*sum(list_count_together_to_be_appart)
        # +8*(count_gp_8_assigned-count_gp_8_intern_together)
        )
    basic_wards_values = [duty_shifts[(gp,d,w)] for d in range(len(prev_duty_shift),num_days) for w in all_wards ]
    psych_wards_values = [duty_shifts[(gp,d,'PSYCH')] for d in range(len(prev_duty_shift),num_days) if is_psych_not(d,len(prev_duty_shift),is_first_day_psych)]
    ART_values = [duty_shifts[(gp,d,'ART')] for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
    model.add_decision_strategy(
        basic_wards_values+psych_wards_values+ART_values,
        cp_model.CHOOSE_LOWEST_MIN,
        cp_model.SELECT_MIN_VALUE
    )
    print('logic len psych',len(psych_wards_values))
    #solver logic
    solver = cp_model.CpSolver()
    #first solve with randomization to check feasibility
    # solver.parameters.log_search_progress = True
    # solver.parameters.max_time_in_seconds= 60*3 #02 minutes
    # solver.parameters.random_seed = 12
    # solver.parameters.randomize_search = True
    # solver.parameters.use_lns = True
    # solver.parameters.use_lb_relax_lns = True
    # solver.parameters.use_lns_only = False
    # trial_status = solver.solve(model)
    # if trial_status == cp_model.OPTIMAL or trial_status == cp_model.FEASIBLE:
    #     hints = {}
    #     for d in range(len(prev_duty_shift),num_days):
    #         for w in all_wards: 
    #             for t in duty_types:
    #                 if is_skippable(d,w,t):
    #                     continue
    #                 for gp in all_gps:
    #                     hints[duty_shifts[(gp,d,w,t)].Index()]=solver.value(duty_shifts[(gp,d,w,t)])
        
    #     for key, value in hints.items():
    #         model.add_hint(key,value)
    #second solve with no randomization
    #one solver method
    solver.parameters.max_time_in_seconds= 60*d_max_min
    solver.parameters.log_search_progress = True
    #default and randomize
    solver.parameters.random_seed = 48
    solver.parameters.randomize_search = True
    # solver.parameters.search_random_variable_pool_size = 30
    # solver.parameters.use_overload_checker_in_cumulative = False
    solver.parameters.add_clique_cuts = True
    solver.parameters.add_objective_cut = True
    #make the search aggressive
    # solver.parameters.search_branching = cp_model.FIXED_SEARCH
    solver.parameters.use_sat_inprocessing = True
    solver.parameters.use_objective_lb_search = True
    solver.parameters.use_feasibility_pump = True
    solver.parameters.use_feasibility_jump = True
    solver.parameters.use_extended_probing = True
    solver.parameters.use_blocking_restart = True
    solver.parameters.use_objective_shaving_search = True
    #solver performance
    #solver.parameters.num_search_workers = 4 
    solver.parameters.cp_model_presolve = True
    solver.parameters.cp_model_probing_level = 2 #agrresive assignment and pruning done on presolve
    solver.parameters.optimize_with_core= True #uses unsat to prune out imposible bounds on presolve
    solver.parameters.optimize_with_max_hs = True #works with optimize_with_core increase effeciency
    # solver.parameters.optimize_with_lb_tree_search = True #experimental; don't use it #tree based lower bound chasing to prune it if lower than current best
    solver.parameters.linearization_level = 3 #high optimazation required for multiple boolvar and intvar
    solver.parameters.use_lns = True #LNS (large neighberhood search)
    solver.parameters.use_lns_only = False
    solver.parameters.use_lb_relax_lns = True #fancy lns 
    solver.parameters.use_rins_lns = True
    # solver.parameters.polish_lp_solution = True
    solver.parameters.use_dual_scheduling_heuristics = True
    callback = Solution_Callback(solver,stop_event)
    status = solver.solve(model,callback)
    #After solution found or infesible
    duty_solution = {}
    if status != cp_model.FEASIBLE:
        print("Not Feasible")
        msg_queue.put("Not Feasible\n")
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        end_event.set()
        print("Solution:")
        msg_queue.put("Solution:\n")
        for d in range(len(prev_duty_shift),num_days): #change to range(len(prev_duty_shift),num_days) after editing
            duty_solution[d] = {}
            print(d,":")
            msg_queue.put(f'{d}:\n')
            for w in all_wards:
                print('\t',w,end=":")
                msg_queue.put(f'\t{w}:')
                for gp in all_gps:
                    if solver.value(duty_shifts[(gp,d,w)]) == 1:
                        print(f'(gp_{gp})',end=' ')
                        msg_queue.put(f'(gp_{gp}) ')
                        duty_solution[d][(w)] = gp
                print("")
                msg_queue.put("\n")
            if d>=len(prev_duty_shift) and is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
                w='PSYCH'
                print('\t',w,end=":")
                msg_queue.put(f'\t{w}:')
                for gp in all_gps:
                    if solver.value(duty_shifts[(gp,d,w)]) == 1:
                        print(f'(gp_{gp})',end=' ')
                        msg_queue.put(f'(gp_{gp}) ')
                        duty_solution[d][(w)] = gp
                print("")
                msg_queue.put("\n")
            dow = get_day_of_week(d)
            if dow == 5 or dow == 6 or d in holiday_date_index:
                w = 'ART'
                print('\t',w,end=":")
                msg_queue.put(f'\t{w}:')
                for gp in all_gps:
                    if solver.value(duty_shifts[(gp,d,w)]) == 1:
                        print(f'(gp_{gp})',end=' ')
                        msg_queue.put(f'(gp_{gp}) ')
                        duty_solution[d][(w)] = gp
                print("")
                msg_queue.put("\n")
            # for iww in intern_duty_wards:
            #     if d>=len(prev_duty_shift) and solver.value(intern_duty_shifts[(d,iww)])==1:
            #         print(f'intern_{iww}')
                    
        print("Optimized: ",solver.objective_value)
        msg_queue.put(f'Optimized: {solver.objective_value}\n')
        print("Max hr", solver.value(max_hr),
              "; Min hr", solver.value(min_hr),
              "; Avg hr", solver.value(avg_hr),
              "; MaxE hr", solver.value(max_eff_hr),
              "; MinE hr", solver.value(min_eff_hr),
              "; MinMon hr", solver.value(min_mon_hr)/mul_hr_scale,
              "; MmaxMon hr", solver.value(max_mon_hr)/mul_hr_scale,
              "; Max_sig hr", solver.value(max_signed_hrs),
              "; Min_sig hr", solver.value(min_signed_hrs),
            # "; cgp8it", solver.value(count_gp_8_assigned)-solver.value(count_gp_8_intern_together),
              "; MaxWd hr", solver.value(max_weekend_hol_hrs),
              "; MinWd hr", solver.value(min_weekend_hol_hrs),
              "; MaxES hr", solver.value(max_eff_signed_hr),
              "; MinES hr", solver.value(min_eff_signed_hr),
              "; tg sum", solver.value(sum(list_count_together_to_be_appart)),
              "; tg 2_1", solver.value(count_gp_2_assigned)-solver.value(count_gp_2_1_together),
              "; IMW E diff", solver.value(max_imw_num)-solver.value(min_imw_num),
              )
        msg_queue.put(f'''Max hr {solver.value(max_hr)};Min hr {solver.value(min_hr)};Avg hr {solver.value(avg_hr)};Max_signed hr {solver.value(max_signed_hrs)};Min_signed hr {solver.value(min_signed_hrs)}\n'''
              )
        for gp in all_gps:
            print(
                f"gp_{gp}=>",
                solver.value(cal_gp_hrs[gp]),'hrs;',
                solver.value(cal_gp_imw_num[gp]),' imw;',
                solver.value(cal_gp_imw_weekend_num[gp]),' weekend;', 
                solver.value(cal_gp_weekend_hol_num[gp]),' total weekend;',
                solver.value(cal_gp_signed_hrs[gp]),'hr signed;',
                solver.value(cal_gp_weekend_hol_hrs[gp]),'hr weekend;',
                solver.value(mon_gp_hrs[gp]),'hr money;'
            )
            msg_queue.put(f'''gp_{gp}=> {solver.value(cal_gp_hrs[gp])} hrs; 
                          \t\t{solver.value(cal_gp_imw_num[gp])} imw; 
                          \t\t{solver.value(cal_gp_imw_weekend_num[gp])} imw weekend;
                          \t\t{solver.value(cal_gp_weekend_hol_num[gp])} total weekend;
                          \t\t{solver.value(mon_gp_hrs[gp])} hr money;
                          \t\t{solver.value(cal_gp_signed_hrs[gp])} hr signed\n''')
    else:
        print("No optimal solution found")
        msg_queue.put("No optimal solution found\n")
    return duty_solution

def csv_all_column_writer(duty_solution:dict,all_wards:list,first_day_index:int,holiday_date_index:list):
    with open('duty_csv.csv','w',newline='') as f:
            fieldnames = [f"{w}" for w in all_wards]
            writer = csv.DictWriter(f,fieldnames=fieldnames)
            for d, dict_each_day in duty_solution.items():
                #for each day
                day_duty = {}
                for (w), gp in dict_each_day.items():
                    day_duty[f"{w}"]=gp
                writer.writerow(day_duty)
    with open('duty_csv_for_test.csv','w',newline='') as f:
        ward_types = [f"{w}" for w in all_wards]
        fieldnames = ['date']
        fieldnames.extend(ward_types)
        writer = csv.DictWriter(f,fieldnames=fieldnames)
        for d, dict_each_day in duty_solution.items():
            #for each day
            t_0 = {w:gp for (w),gp in dict_each_day.items()}
            t_0['date']=d
            # t_1 = {w:gp for (w,t),gp in dict_each_day.items() if t == duty_types[1]}
            # t_1['date']=d
            writer.writerows([t_0])
    check_values_csv(holiday_date_index=holiday_date_index, first_day_index=first_day_index)

def csv_ward_based_col(duty_solution:dict,all_wards:list,first_day_index:int,holiday_date_index:list):
    with open('duty_csv.csv','w',newline='') as f:
            ward_types = [f"{w}" for w in all_wards]
            fieldnames = ['date']
            fieldnames.extend(ward_types)
            writer = csv.DictWriter(f,fieldnames=fieldnames)
            for d, dict_each_day in duty_solution.items():
                #for each day
                t_0 = {w:gp for (w),gp in dict_each_day.items()}
                t_0['date']=d
                # t_1 = {w:gp for (w,t),gp in dict_each_day.items() if t == duty_types[1]}
                writer.writerows([t_0])
    with open('duty_csv_for_test.csv','w',newline='') as f:
            ward_types = [f"{w}" for w in all_wards]
            fieldnames = ['date']
            fieldnames.extend(ward_types)
            writer = csv.DictWriter(f,fieldnames=fieldnames)
            for d, dict_each_day in duty_solution.items():
                #for each day
                t_0 = {w:gp for (w),gp in dict_each_day.items()}
                t_0['date']=d
                # t_1 = {w:gp for (w,t),gp in dict_each_day.items() if t == duty_types[1]}
                # t_1['date']=d
                writer.writerows([t_0])
    check_values_csv(holiday_date_index=holiday_date_index, first_day_index=first_day_index)

class DayDuty:
    def __init__(self) -> None:
        self.all_wards = super_all_wards
        # self.duty_types = ['actual','signed']
        self._data = {}
    def day_data(self)-> dict:
        return self._data
    def c_w4(self,av,sv=None):
        if av:
            self._data[(self.all_wards[0])]=av
        # if sv:
        #     self._data[(self.all_wards[0],self.duty_types[1])]=sv
        return self
    def c_w4f(self,av,sv=None):
        if av:
            self._data[(self.all_wards[1])]=av
        # if sv:
        #     self._data[(self.all_wards[1],self.duty_types[1])]=sv
        return self
    def c_w9(self,av,sv=None):
        if av:
            self._data[(self.all_wards[1])]=av
        # if sv:
        #     self._data[(self.all_wards[2],self.duty_types[1])]=sv
        return self
    def c_mdr(self,av,sv=None):
        if av:
            self._data[(self.all_wards[2])]=av
        # if sv:
        #     self._data[(self.all_wards[3],self.duty_types[1])]=sv
        return self
    def c_imw(self,av,sv=None):
        if av:
            self._data[(self.all_wards[3])]=av
        # if sv:
        #     self._data[(self.all_wards[4],self.duty_types[1])]=sv
        return self
    def c_art(self,av,sv=None):
        if av:
            self._data[(self.all_wards[4])]=av
        # if sv:
        #     self._data[(self.all_wards[5],self.duty_types[1])]=sv
        return self
    def c_psych(self,av=None,sv=None):
        if av:
            self._data[(self.all_wards[5])]=av
        # if sv:
        #     self._data[(self.all_wards[6],self.duty_types[1])]=sv
        return self
    def d_ward(self,w,av,sv=None):
        if(w==self.all_wards[0]):self.c_w4(av,sv)
        # elif(w==all_wards[1]):self.c_w4f(av,sv)
        elif(w==self.all_wards[1]):self.c_w9(av,sv)
        elif(w==self.all_wards[2]):self.c_mdr(av,sv)
        elif(w==self.all_wards[3]):self.c_imw(av,sv)
        elif(w==self.all_wards[4]):self.c_art(av,sv)
        elif(w==self.all_wards[5]):self.c_psych(av,sv)

if __name__ == "__main__":
    all_wards = super_all_wards
    # duty_types = ['actual','signed']
    d_first_day_index = 3
    d_holiday_dates = []
    d_prev_duty_shift_new={
            0: DayDuty().c_w4(7).c_w9(12).c_imw(0).day_data(),
            # 1: DayDuty().c_w4(1).c_w9(2).c_imw(11).day_data(),
            # 2: DayDuty().c_w4(4).c_w9(5).c_imw(6).day_data(),
    }
    duty_solution = main(
        d_num_gps=14,
        d_num_days=30,
        d_freedays_after_duty=2,
        d_is_first_day_psych=False,
        d_holiday_dates=d_holiday_dates,
        d_first_day_index=d_first_day_index,
        d_prev_duty_shift_new=d_prev_duty_shift_new,
        d_max_min=1*0.2,
        # d_max_min=5,
        # d_prev_duty_shift=[
        #     {all_wards[0]:14,all_wards[1]:5,all_wards[2]:7,all_wards[4]:[3,15]},
        #     {all_wards[0]:4,all_wards[1]:16,all_wards[2]:12,all_wards[4]:[2,6]},
        #     {all_wards[0]:9,all_wards[1]:13,all_wards[2]:1,all_wards[4]:[10,11]}
        # ]
    )
    # csv_ward_based_col(duty_solution,all_wards,duty_types) #temp
    csv_decision = input("Do you want to create a CSV?[Y,N]").strip().lower()
    if csv_decision == 'y':
        # csv_all_column_writer(duty_solution,all_wards,duty_types)
        holiday_date_index = list(map(lambda x: x-1 if x-1>=0 else 0,d_holiday_dates))
        csv_ward_based_col(duty_solution,all_wards,d_first_day_index,holiday_date_index)
    else:
        sys.exit()
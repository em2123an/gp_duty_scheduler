from ortools.sat.python import cp_model
import sys
import csv

def main():

    model = cp_model.CpModel()
    days_of_week=['mon','tue','wed','thr','fri','sat','sun']
    all_wards = ['W4M','W4F','W9','MDR','IMW']
    hrs_per_week = {
        days_of_week[0]: int(16*1.5), days_of_week[1]: int(16*1.5), days_of_week[2]: int(16*1.5),days_of_week[3]: int(16*1.5),
        days_of_week[4]: int(17*1.5),
        days_of_week[5]: int(24*1.5),days_of_week[6]: int(24*1.5)
    }
    ART_hrs = 8
    duty_types = ['actual','signed']
    duty_types_2 = ['actual','actual']

    prev_duty_shift={
        0:{
            (all_wards[0],duty_types[0]): 0, #w4m_a
            (all_wards[1],duty_types[0]): 2, #w4f_a
            (all_wards[2],duty_types[0]): 4, #w9_a
            (all_wards[4],duty_types[0]): 12, #imw_a
            (all_wards[4],duty_types[1]): 5, #imw_s
        },
        1:{
            (all_wards[0],duty_types[0]): 3, #w4m_a
            (all_wards[1],duty_types[0]): 16, #w4f_a
            (all_wards[2],duty_types[0]): 10, #w9_a
            (all_wards[4],duty_types[0]): 8, #imw_a
            (all_wards[4],duty_types[1]): 6, #imw_s
        },
        2:{
            (all_wards[0],duty_types[0]): 11, #w4m_a
            (all_wards[1],duty_types[0]): 1, #w4f_a
            (all_wards[2],duty_types[0]): 15, #w9_a
            (all_wards[4],duty_types[0]): 14, #imw_a
            (all_wards[4],duty_types[1]): 9, #imw_s
        },
    }
    

    # num_gps = 40
    num_gps = 17
    num_days = 33
    first_day_index = 2
    freedays_after_duty = 2
    is_first_day_psych = False

    all_gps = range(num_gps)
    all_days = range(num_days)

    duty_shifts={}

    def get_day_of_week(d,first_day_index=first_day_index):
        return int(d+first_day_index)%(len(days_of_week)) if (d+first_day_index)>=len(days_of_week) else int(d+first_day_index)
    
    def is_w4_weekday_signeds(d,w,t):
        dow = get_day_of_week(d)
        if dow != 5 and dow != 6 and w in [all_wards[0],all_wards[1]] and t==duty_types[1]:
            return True
        return False
    
    def is_psych_not(d,first_d, is_first_day_true):
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

    #create boolean variable for all possible combination
    for gp in all_gps:
        for d in all_days:
            for w in all_wards:
                for t in duty_types:
                    if is_w4_weekday_signeds(d,w,t):
                        continue
                    duty_shifts[(gp,d,w,t)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}")
    #create boolean variable for art
    for d in all_days:
        dow = get_day_of_week(d)
        if dow == 5 or dow == 6:
            w = 'ART'
            for gp in all_gps:
                for t in duty_types:
                    duty_shifts[(gp,d,w,t)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}")
    #create boolean variable for psych
    for d in range(len(prev_duty_shift),num_days):
        if is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
            w='PSYCH'
            t=duty_types[1]
            for gp in all_gps:
                duty_shifts[(gp,d,w,t)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}")

    # def cal_gp_hr_difference():
    #     hr_per_gp = {}
    #     for gp in all_gps:
    #         hr_count = 0
    #         for d in all_days:
    #             dow = int(d+first_day_index)%(len(days_of_week)) if (d+first_day_index)>=len(days_of_week) else int(d+first_day_index)
    #             hr_count += sum(duty_shifts[(gp,d,w,t)]*hrs_per_week[days_of_week[dow]] for w in all_wards for t in duty_types)
    #         hr_per_gp[gp] = hr_count
    #     print(hr_per_gp)
    #     return stats.variance(hr_per_gp[gp] for gp in all_gps)
    
    #add rules (constraints)
    #rule 1: each duty needs to be covered by exactly one gp
    for d in all_days:
        for w in all_wards:
            for t in duty_types:
                if is_w4_weekday_signeds(d,w,t):
                        continue
                model.add_exactly_one(duty_shifts[(gp,d,w,t)] for gp in all_gps)
        if d>=len(prev_duty_shift) and is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
            model.add_exactly_one([duty_shifts[(gp,d,'PSYCH',duty_types[1])] for gp in all_gps])
    #rule 2:one gp can at most have one duty per day
    for gp in all_gps:
        for d in all_days:
            dow = get_day_of_week(d)
            basic_wards = [duty_shifts[(gp,d,w,t)] for w in all_wards for t in duty_types if not is_w4_weekday_signeds(d,w,t)]
            art_ward = [duty_shifts[(gp,d,'ART',t)] for t in duty_types if dow==5 or dow==6]
            if d>=len(prev_duty_shift) and is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
                psych_ward=[duty_shifts[(gp,d,'PSYCH',duty_types[1])]]
            else:
                psych_ward = []
            model.add_at_most_one(basic_wards + art_ward + psych_ward)
    #rule 3: each gp should cover IMW before repeating the cycle
    duty_cycle_day = num_gps // len(duty_types)
    duty_for_num_days = num_days//duty_cycle_day
    for gp in all_gps:
        if duty_for_num_days!=0 :
            w = all_wards[4]
            for d in all_days:
                for cc in range(duty_for_num_days):
                    i=cc*duty_cycle_day+d if cc*duty_cycle_day+d<num_days else num_days
                    j=(cc+1)*duty_cycle_day+d if (cc+1)*duty_cycle_day+d<num_days else num_days
                    model.add_at_most_one(duty_shifts[(gp,dd,w,t)] for t in duty_types for dd in range(i,j))
    # #rule 4: each gp should one have one countable (actual entered) in 03 days
    countable_wards = all_wards.copy()
    countable_wards.remove('MDR')
    for gp in all_gps:
        # freedays_after_duty = 2
        for w in countable_wards:
            for t in duty_types:
                if t==duty_types[1] and w!=all_wards[4]:
                    continue
                for d in all_days:
                    if is_w4_weekday_signeds(d,w,t):
                        continue
                    i = d
                    j = d+freedays_after_duty+1 if d+freedays_after_duty+1<num_days else num_days
                    gen_all_assigned = [duty_shifts[(gp,dd,ww,duty_types[0])] for dd in range(i,j) for ww in countable_wards]
                    gen_imw_signed = [duty_shifts[(gp,dd,all_wards[4],duty_types[1])] for dd in range(i,j)]
                    model.add_at_most_one(
                        gen_all_assigned
                        # +gen_imw_signed
                        )
                    # model.add_at_most_one(duty_shifts[(gp,dd,ww,duty_types[0])] for dd in range(i,j) for ww in countable_wards)
    #rule 5: use previous shift to prevent overlaps
    # prev_duty_bool_vars = []
    # for dd, dict1 in prev_duty_shift.items():
    #     for (ww,tt), old_gp in dict1.items():
    #         prev_duty_bool_vars.append(duty_shifts[(old_gp,dd,ww,tt)])
    # model.add_bool_and(prev_duty_bool_vars)
    for dd, dict1 in prev_duty_shift.items():
        for (ww,tt), old_gp in dict1.items():
            model.add(duty_shifts[(old_gp, dd, ww, tt)] == 1)

    #rule 6: Adding ART (other dependent ward)
    for d in all_days:
        dow = get_day_of_week(d)
        if dow == 5 or dow == 6:
            w = 'ART'
            ART_possible_ward = all_wards.copy()
            ART_possible_ward.remove('MDR')
            ART_possible_ward.remove('IMW')
            # for gp in all_gps:
            #     for t in duty_types:
            #         duty_shifts[(gp,d,w,t)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}")
            for gp in all_gps:
                one_day_back = d-1 if d-1>=0 else 0
                prev_day_duty_gp_values = [duty_shifts[(gp,one_day_back,ww,duty_types[0])] for ww in ART_possible_ward]
                curr_day_duty_gp_values = [duty_shifts[(gp,d,w,tt)] for tt in duty_types]
                #curr_day_duty_gp_values = [duty_shifts[(gp,d,w,duty_types[0])]] #want to use just actual not signed for one day back rule
                pddgv = model.new_bool_var(f"prev_gp{gp}_d{d}_w{w}_t{t}")
                cddgv = model.new_bool_var(f"curr_gp{gp}_d{d}_w{w}_t{t}")
                model.add_bool_or(prev_day_duty_gp_values).only_enforce_if(pddgv)
                model.add_bool_or(curr_day_duty_gp_values).only_enforce_if(cddgv)
                model.add(sum(curr_day_duty_gp_values)==0).only_enforce_if(pddgv.Not())
            for t in duty_types:
                model.add_exactly_one(duty_shifts[(gp,d,w,t)] for gp in all_gps)
            for gp in all_gps:
                model.add_at_most_one(duty_shifts[(gp,d,w,t)] for t in duty_types)
    #optimization if needed
    cal_gp_hrs={}
    max_hr = model.new_int_var(0,24*num_days,f"max_gp_hrs")
    min_hr = model.new_int_var(0,24*num_days,f"min_gp_hrs")
    avg_hr = model.new_int_var(0,24*num_days,f"avg_gp_hrs")
    total_hr = model.new_int_var(0,24*num_days*num_gps,f"total_gp_hrs")
    cal_gp_imw_num = {}
    max_imw_num = model.new_int_var(0,num_days,f"max_gp_imw_num")
    min_imw_num = model.new_int_var(0,num_days,f"min_gp_imw_num")
    cal_gp_signed_hrs = {}
    max_signed_hrs = model.new_int_var(0,24*num_days,f"max_gp_signed_hrs")
    min_signed_hrs = model.new_int_var(0,24*num_days,f"min_gp_signed_hrs")
    cal_gp_weekend_num = {}
    max_weekend_num = model.new_int_var(0,(num_days//7)-1,f"max_gp_weekend_num")
    min_weekend_num = model.new_int_var(0,(num_days//7)-1,f"min_gp_weekend_num")
    cal_gp_imw_weekend_num = {}
    max_imw_weekend_num = model.new_int_var(0,(num_days//7)+1,f"max_gp_imw_weekend_num")
    min_imw_weekend_num = model.new_int_var(0,(num_days//7)+1,f"min_gp_imw_weekend_num")
    for gp in all_gps:
        #calculate hours for each gp
        cal_gp_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_hrs({gp})")
        basic_wards_hrs_values = [duty_shifts[(gp,d,w,t)]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) for w in all_wards for t in duty_types if not is_w4_weekday_signeds(d,w,t)]
        psych_wards_hrs_values = [duty_shifts[(gp,d,'PSYCH',duty_types[1])]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) if is_psych_not(d,len(prev_duty_shift),is_first_day_psych)]
        ART_hrs_values = [duty_shifts[(gp,d,'ART',t)]*ART_hrs for t in duty_types for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
        model.add(cal_gp_hrs[gp]==sum(basic_wards_hrs_values + ART_hrs_values + psych_wards_hrs_values))
        model.add(cal_gp_hrs[gp]<=max_hr)
        model.add(cal_gp_hrs[gp]>=min_hr)
        #calculate signed hours for each gp
        cal_gp_signed_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_signed_hrs({gp})")
        basic_wards_signed_hrs_values = [duty_shifts[(gp,d,w,duty_types[1])]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) for w in all_wards if (not is_w4_weekday_signeds(d,w,duty_types[1])) and w!=all_wards[4]]
        MDR_actual_as_signed_hr = [duty_shifts[(gp,d,all_wards[3],duty_types[0])]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days)]
        ART_signed_hrs_values = [duty_shifts[(gp,d,'ART',t)]*ART_hrs if get_day_of_week(d) == 6 else duty_shifts[(gp,d,'ART',duty_types[1])]*ART_hrs for t in duty_types for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
        model.add(cal_gp_signed_hrs[gp]==sum(
            basic_wards_signed_hrs_values 
            +MDR_actual_as_signed_hr
            +ART_signed_hrs_values
            +psych_wards_hrs_values
            ))
        model.add(cal_gp_signed_hrs[gp]<=max_signed_hrs)
        model.add(cal_gp_signed_hrs[gp]>=min_signed_hrs)
        #calculate how many imw entry
        cal_gp_imw_num[gp] = model.new_int_var(0,num_days,f"gp_imw_num({gp})")
        imw_num_by_each_gp = [duty_shifts[(gp,d,all_wards[4],t)] for d in range(len(prev_duty_shift),num_days) for t in duty_types]
        model.add(cal_gp_imw_num[gp]==sum(imw_num_by_each_gp))
        model.add(cal_gp_imw_num[gp]<=max_imw_num)
        model.add(cal_gp_imw_num[gp]>=min_imw_num)
        #calculate how many weekend entry
        cal_gp_weekend_num[gp] = model.new_int_var(0,num_days,f"gp_weekend_num({gp})")
        weekend_all_assigned = [duty_shifts[(gp,d,ww,duty_types[0])] for ww in countable_wards for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
        weekend_imw_signed = [duty_shifts[(gp,d,all_wards[4],duty_types[1])]  for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
        model.add(cal_gp_weekend_num[gp]==sum(weekend_all_assigned + weekend_imw_signed))
        model.add(cal_gp_weekend_num[gp]<=max_weekend_num)
        model.add(cal_gp_weekend_num[gp]>=min_weekend_num)
        #calculate how many weekend imw entry
        cal_gp_imw_weekend_num[gp] = model.new_int_var(0,num_days,f"gp_imw_weekend_num({gp})")
        weekend_imw_num = [duty_shifts[(gp,d,all_wards[4],t)] for t in duty_types  for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
        model.add(cal_gp_imw_weekend_num[gp]==sum(weekend_imw_num))
        model.add(cal_gp_imw_weekend_num[gp]<=max_imw_weekend_num)
        model.add(cal_gp_imw_weekend_num[gp]>=min_imw_weekend_num)
    #calculate average gp hours
    model.add(total_hr==sum([cal_gp_hrs[gp] for gp in all_gps]))
    # model.add(avg_hr*num_gps == sum([cal_gp_hrs[gp] for gp in all_gps]))
    # model.add(total_hr == avg_hr * num_gps)
    model.add_division_equality(avg_hr,total_hr,num_gps)

    #personalized preferrences
    #GP_9 will not be working on sundays
    for d in all_days:
        dow = get_day_of_week(d)
        if dow == 6:
            agp = 9
            agp_values = [duty_shifts[(agp,d,w,t)] if w==all_wards[4] else duty_shifts[(agp,d,w,duty_types[0])] for w in countable_wards for t in duty_types]
            model.add(sum(agp_values)==0) 
    #GP-16: can't be on duty on tuesday; on saturday = be in intermediate
    for d in all_days:
        agp = 16
        dow= get_day_of_week(d)
        #tuesday rule
        if dow==1:
            agp_values = [duty_shifts[(agp,d,w,t)] if w==all_wards[4] else duty_shifts[(agp,d,w,duty_types[0])] for w in countable_wards for t in duty_types if not is_w4_weekday_signeds(d,w,t)]   
            model.add(sum(agp_values)==0)
        #saturday intermediate rule
        if dow == 5:
            agp_values = [duty_shifts[(agp,d,w,duty_types[0])] for w in countable_wards if w!=all_wards[4]]
            model.add(sum(agp_values)==0)
    #make gp 15 in same duty with gp 11 as much as possible
    count_gp_15_assigned = model.new_int_var(0,num_days,f"gp_15_assigned_count")
    assigned_values_gp_15 = [duty_shifts[(15,d,w,t)] if w == all_wards[4] else duty_shifts[(15,d,w,duty_types[0])] for d in all_days for w in countable_wards for t in duty_types if not is_w4_weekday_signeds(d,w,t)]
    model.add(count_gp_15_assigned==sum(assigned_values_gp_15))
    list_gp_15_11_together=[]
    for d in all_days:
        has_gp15_enter = model.new_bool_var(f"has_gp15_on{d}")
        has_gp11_enter = model.new_bool_var(f"has_gp11_on{d}")
        model.add_max_equality(has_gp15_enter,[duty_shifts[(15,d,w,t)] if w == all_wards[4] else duty_shifts[(15,d,w,duty_types[0])] for w in countable_wards for t in duty_types if not is_w4_weekday_signeds(d,w,t)])
        model.add_max_equality(has_gp11_enter,[duty_shifts[(11,d,w,t)] if w == all_wards[4] else duty_shifts[(11,d,w,duty_types[0])] for w in countable_wards for t in duty_types if not is_w4_weekday_signeds(d,w,t)])
        mark_d = model.new_bool_var(f"mark_{d}_{15}_{11}")
        model.add_bool_and([has_gp11_enter,has_gp15_enter]).only_enforce_if(mark_d)
        model.add_bool_or([has_gp11_enter.Not(),has_gp15_enter.Not()]).only_enforce_if(mark_d.Not())
        list_gp_15_11_together.append(mark_d)
    count_gp_15_11_together = model.new_int_var(0,num_days,f"count_gp_15_11_together")
    model.add(count_gp_15_11_together==sum(list_gp_15_11_together))
    #compensating old mishaps
    model.add(cal_gp_hrs[5]==max_hr)
    # model.add(cal_gp_hrs[8]>=max_hr-2)
    # model.add(cal_gp_hrs[12]>=max_hr-2)
    # def mishap_gen (value_list,gp,avg_hr,constant):
    #     comp_gp_hr_constant = model.new_int_var(num_days*24*-100,num_days*24*100,f"comp_gp_hr_{gp}")
    #     # model.add(comp_gp_hr_constant==4*(cal_gp_hrs[gp]-(avg_hr+constant)))
    #     model.add_abs_equality(comp_gp_hr_constant,cal_gp_hrs[gp]-(avg_hr+constant))
    #     value_list.append(comp_gp_hr_constant)
    # comp_gp_value_list = []
    # #mishap_gen(comp_gp_value_list,0,avg_hr,-10)
    # #mishap_gen(comp_gp_value_list,4,avg_hr,-25)
    # mishap_gen(comp_gp_value_list,5,avg_hr,22)
    # #mishap_gen(comp_gp_value_list,6,avg_hr,61)
    # #mishap_gen(comp_gp_value_list,7,avg_hr,-11)
    # mishap_gen(comp_gp_value_list,8,avg_hr,22)
    # #mishap_gen(comp_gp_value_list,11,avg_hr,-4)
    # mishap_gen(comp_gp_value_list,12,avg_hr,25)
    # for gp in all_gps:
    #     list_comp_gps = [0,4,5,8,11,12]
    #     if gp not in list_comp_gps:
    #         mishap_gen(comp_gp_value_list,gp,avg_hr,0)
    # comp_gp_value_list.append(cal_gp_hrs[0]-(avg_hr-39.4))
    # comp_gp_value_list.append(cal_gp_hrs[4]-(avg_hr-44.4))
    # comp_gp_value_list.append(cal_gp_hrs[5]-(avg_hr+51.6))
    # comp_gp_value_list.append(cal_gp_hrs[6]-(avg_hr+60.6))
    # comp_gp_value_list.append(cal_gp_hrs[7]-(avg_hr-11.4))
    # comp_gp_value_list.append(cal_gp_hrs[8]-(avg_hr-35.6))
    # comp_gp_value_list.append(cal_gp_hrs[9]-(avg_hr-12.4))
    # comp_gp_value_list.append(cal_gp_hrs[9]-(avg_hr+18.6))
    # comp_gp_value_list.append(cal_gp_hrs[9]-(avg_hr-18.4))
    #optimization functions
    # fairness_minimizer = model.new_int_var(0,24*num_days*num_gps*100,f"fairness_minimizer")
    # model.add(fairness_minimizer==4*(max_hr-min_hr)+2*(max_weekend_num-min_weekend_num)+4*(max_signed_hrs-min_signed_hrs))
    # compensation_minimizer = model.new_int_var(num_days*24*-100,num_days*24*100,f"compensation_minimizer")
    # model.add(compensation_minimizer==2*(cal_gp_hrs[5]-cal_gp_hrs[8])+3*(cal_gp_hrs[5]-cal_gp_hrs[12]))
    # model.minimize(4*fairness_minimizer + compensation_minimizer)
    #model.minimize(fairness_minimizer+(count_gp_15_assigned-count_gp_15_11_together))``
    model.minimize(
        4*(max_hr-min_hr)+2*(max_weekend_num-min_weekend_num)+4*(max_signed_hrs-min_signed_hrs)
        +2*(cal_gp_hrs[5]-cal_gp_hrs[8])+3*(cal_gp_hrs[5]-cal_gp_hrs[12])
        +2*(count_gp_15_assigned-count_gp_15_11_together)
        )
    #solver logic
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds= 60*20
    solver.parameters.log_search_progress = True
    solver.parameters.cp_model_presolve = True
    status = solver.solve(model)
    # solver.solve(model)
    # opt_hrs_worked = solver.value(max_hr)-solver.value(min_hr)
    # model.add(max_hr-min_hr==opt_hrs_worked)
    # model.minimize(max_weekend_num-min_weekend_num)
    # status = solver.solve(model)
    duty_solution = {}
    if status != cp_model.FEASIBLE:
        print("Not Feasible")
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("Solution:")
        for d in all_days:
            duty_solution[d] = {}
            print(d,":")
            for w in all_wards:
                print('\t',w,end=":")
                for t in duty_types:
                    if is_w4_weekday_signeds(d,w,t):
                        #duty_solution[(d,w,t)] = " "
                        continue
                    for gp in all_gps:
                        if solver.value(duty_shifts[(gp,d,w,t)]) == 1:
                            print(f'{t}(gp_{gp})',end=' ')
                            duty_solution[d][(w,t)] = gp
                print("")
            if d>=len(prev_duty_shift) and is_psych_not(d,len(prev_duty_shift),is_first_day_psych):
                w='PSYCH'
                t=duty_types[1]
                print('\t',w,end=":")
                for gp in all_gps:
                        if solver.value(duty_shifts[(gp,d,w,t)]) == 1:
                            print(f'(gp_{gp})',end=' ')
                            duty_solution[d][(w,t)] = gp
                print("")
            dow = get_day_of_week(d)
            if dow == 5 or dow == 6:
                w = 'ART'
                print('\t',w,end=":")
                for t in duty_types:
                    for gp in all_gps:
                        if solver.value(duty_shifts[(gp,d,w,t)]) == 1:
                            print(f'{t}(gp_{gp})',end=' ')
                            duty_solution[d][(w,t)] = gp
                print("")
        print("Optimized: ",solver.objective_value)
        print("Max hr", solver.value(max_hr),
              "; Min hr", solver.value(min_hr),
              "; Avg hr", solver.value(avg_hr),
              "; Max_signed hr", solver.value(max_signed_hrs),
              "; Min_signed hr", solver.value(min_signed_hrs)
              )
        for gp in all_gps:
            print(f"gp_{gp}=>",solver.value(cal_gp_hrs[gp]),' hrs;',solver.value(cal_gp_imw_num[gp]),' imw-',solver.value(cal_gp_imw_weekend_num[gp]),'weekend', solver.value(cal_gp_weekend_num[gp]),' total weekend;',solver.value(cal_gp_signed_hrs[gp]),'hr signed')
    else:
        print("No optimal solution found")
    return duty_solution

if __name__ == "__main__":
    all_wards = ['W4M','W4F','W9','MDR','IMW','ART','PSYCH']
    duty_types = ['actual','signed']
    duty_solution = main()
    csv_decision = input("Do you want to create a CSV?[Y,N]").strip().lower()
    if csv_decision == 'y':
        with open('duty_csv.csv','w',newline='') as f:
            # writer = csv.writer(f,"excel")
            fieldnames = [f"{w}_{t}" for w in all_wards for t in duty_types]
            writer = csv.DictWriter(f,fieldnames=fieldnames)
            for d, dict_each_day in duty_solution.items():
                #for each day
                day_duty = {}
                for (w,t), gp in dict_each_day.items():
                    day_duty[f"{w}_{t}"]=gp
                writer.writerow(day_duty)
    else:
        sys.exit()
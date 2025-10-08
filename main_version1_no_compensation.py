from ortools.sat.python import cp_model
import statistics as stats

def main():

    model = cp_model.CpModel()
    days_of_week=['mon','tue','wed','thr','fri','sat','sun']
    all_wards = ['W4M','W4F','W9','MDR','IMW']
    hrs_per_week = {
        days_of_week[0]: 16, days_of_week[1]: 16, days_of_week[2]: 16,days_of_week[3]: 16,
        days_of_week[4]: 17,
        days_of_week[5]: 24,days_of_week[6]: 24
    }
    ART_hrs = 8
    duty_types = ['actual','signed']
    duty_types_2 = ['actual','actual']

    prev_duty_shift={
        0:{
            (all_wards[0],duty_types[0]): 0, #gp_0
            (all_wards[1],duty_types[0]): 1, #gp_1
            (all_wards[2],duty_types[0]): 2, #gp_2
            (all_wards[4],duty_types[0]): 3, #gp_3
            (all_wards[4],duty_types[1]): 4, #gp_4
        },
        1:{
            (all_wards[0],duty_types[0]): 5, #gp_5
            (all_wards[1],duty_types[0]): 6, #gp_6
            (all_wards[2],duty_types[0]): 7, #gp_7
            (all_wards[4],duty_types[0]): 8, #gp_8
            (all_wards[4],duty_types[1]): 9, #gp_9
        },
        2:{
            (all_wards[0],duty_types[0]): 10, #gp_10
            (all_wards[1],duty_types[0]): 11, #gp_12
            (all_wards[2],duty_types[0]): 12, #gp_13
            (all_wards[4],duty_types[0]): 13, #gp_14
            (all_wards[4],duty_types[1]): 14, #gp_15
        },
    }
    

    num_gps = 17
    num_days = 30
    first_day_index = 0
    freedays_after_duty = 2

    all_gps = range(num_gps)
    all_days = range(num_days)

    duty_shifts={}

    #create boolean variable for all possible combination
    for gp in all_gps:
        for d in all_days:
            for w in all_wards:
                for t in duty_types:
                    duty_shifts[(gp,d,w,t)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}")

    def get_day_of_week(d,first_day_index=first_day_index):
        return int(d+first_day_index)%(len(days_of_week)) if (d+first_day_index)>=len(days_of_week) else int(d+first_day_index)

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
                # if(w==all_wards[4]):
                #     t=duty_types[0]
                model.add_exactly_one(duty_shifts[(gp,d,w,t)] for gp in all_gps)
    #rule 2:one gp can at most have one duty per day
    for gp in all_gps:
        for d in all_days:
            model.add_at_most_one(duty_shifts[(gp,d,w,t)] for w in all_wards for t in duty_types)
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
                    i = d
                    j = d+freedays_after_duty+1 if d+freedays_after_duty+1<num_days else num_days
                    gen_all_assigned = [duty_shifts[(gp,dd,ww,duty_types[0])] for dd in range(i,j) for ww in countable_wards]
                    gen_imw_signed = [duty_shifts[(gp,dd,all_wards[4],duty_types[1])] for dd in range(i,j)]
                    model.add_at_most_one(gen_all_assigned+gen_imw_signed)
                    # model.add_at_most_one(duty_shifts[(gp,dd,ww,duty_types[0])] for dd in range(i,j) for ww in countable_wards)
    #rule 5: use previous shift to prevent overlaps
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
            for gp in all_gps:
                for t in duty_types:
                    duty_shifts[(gp,d,w,t)] = model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}")
            for gp in all_gps:
                one_day_back = d-1 if d-1>=0 else 0
                prev_day_duty_gp_values = [duty_shifts[(gp,one_day_back,ww,duty_types[0])] for ww in ART_possible_ward]
                curr_day_duty_gp_values = [duty_shifts[(gp,d,w,tt)] for tt in duty_types]
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
    cal_gp_imw_num = {}
    max_imw_num = model.new_int_var(0,num_days,f"max_gp_imw_num")
    min_imw_num = model.new_int_var(0,num_days,f"min_gp_imw_num")
    cal_gp_weekend_num = {}
    max_weekend_num = model.new_int_var(0,(num_days//7)+1,f"max_gp_weekend_num")
    min_weekend_num = model.new_int_var(0,(num_days//7)+1,f"min_gp_weekend_num")
    cal_gp_imw_weekend_num = {}
    max_imw_weekend_num = model.new_int_var(0,(num_days//7)+1,f"max_gp_imw_weekend_num")
    min_imw_weekend_num = model.new_int_var(0,(num_days//7)+1,f"min_gp_imw_weekend_num")
    for gp in all_gps:
        #calculate hours for each gp
        cal_gp_hrs[gp] = model.new_int_var(0,24*num_days,f"gp_hrs({gp})")
        basic_wards_hrs_values = [duty_shifts[(gp,d,w,t)]*hrs_per_week[days_of_week[get_day_of_week(d)]] for d in range(len(prev_duty_shift),num_days) for w in all_wards for t in duty_types]
        ART_hrs_values = [duty_shifts[(gp,d,'ART',t)]*ART_hrs for t in duty_types for d in range(len(prev_duty_shift),num_days) if get_day_of_week(d) == 5 or get_day_of_week(d) ==6]
        model.add(cal_gp_hrs[gp]==sum(basic_wards_hrs_values + ART_hrs_values))
        model.add(cal_gp_hrs[gp]<=max_hr)
        model.add(cal_gp_hrs[gp]>=min_hr)
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
    
    #optimization functions
    model.minimize(4*(max_hr-min_hr)+3*(max_weekend_num-min_weekend_num)+2*(max_imw_num-min_imw_num)+10*(max_imw_weekend_num-min_imw_weekend_num))
    #solver logic
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds= 50
    status = solver.solve(model)
    # solver.solve(model)
    # opt_hrs_worked = solver.value(max_hr)-solver.value(min_hr)
    # model.add(max_hr-min_hr==opt_hrs_worked)
    # model.minimize(max_weekend_num-min_weekend_num)
    # status = solver.solve(model)
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("Solution:")
        for d in all_days:
            print(d,":")
            for w in all_wards:
                print('\t',w,end=":")
                for t in duty_types:
                    for gp in all_gps:
                        if solver.value(duty_shifts[(gp,d,w,t)]) == 1:
                            print(f'{t}(gp_{gp})',end=' ')
                print("")
            dow = get_day_of_week(d)
            if dow == 5 or dow == 6:
                w = 'ART'
                print('\t',w,end=":")
                for t in duty_types:
                    for gp in all_gps:
                        if solver.value(duty_shifts[(gp,d,w,t)]) == 1:
                            print(f'{t}(gp_{gp})',end=' ')
                print("")
        print("Optimized: ",solver.objective_value)
        print("Max hr", solver.value(max_hr),"; Min hr", solver.value(min_hr))
        for gp in all_gps:
            print(f"gp_{gp}=>",solver.value(cal_gp_hrs[gp]),' hrs;',solver.value(cal_gp_imw_num[gp]),' imw-',solver.value(cal_gp_imw_weekend_num[gp]),'weekend', solver.value(cal_gp_weekend_num[gp]),' total weekend;')
    else:
        print("No optimal solution found")

if __name__ == "__main__":
    main()
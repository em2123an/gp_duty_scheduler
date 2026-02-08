from ortools.sat.python import cp_model
import sys
import csv
import queue
from threading import Event
from check_values import check_values_csv

        # d_num_gps, #total number of gps
        # d_num_days, #total number of days
        # d_first_day_index, #first day index starting from monday as 0
        # d_freedays_after_duty, #freedays to have after each duty
        # d_is_first_day_psych, #is the first day psych or not (boolean)
        # d_max_min, #maximum minute to run the search 
        # d_prev_duty_shift=[], #dict values for all basic wards 
        # d_prev_duty_shift_new = None, #dict values for all basic wards 
        # # d_holiday_dates = [], 
class AtomicScheduleData():
    def __init__(self,value=None, is_available:bool=True, is_entry:bool=True,is_weekend:bool=False,is_holiday:bool=False) -> None:
        super().__init__()
        self.value = value
        self.is_available = is_available
        self.is_entry = is_entry
        self.is_weekend = is_weekend
        self.is_holiday = is_holiday
    def get_value(self):
        return self.value
    def get_is_available(self):
        return self.is_available
    def get_is_entry(self):
        return self.is_entry
    def get_is_holiday(self):
        return self.is_holiday
    def get_is_weekend(self):
        return self.is_weekend
    def get_data(self):
        return {
            "value":self.value,
            "is_available":self.is_available,
            "is_entry":self.is_entry,
            "is_weekend":self.is_weekend,
            "is_holiday":self.is_holiday
        }
    def set_is_weekend(self,value:bool):
        self.is_weekend = value
    def set_is_entry(self,value:bool):
        self.is_entry = value
    def set_is_available(self,value:bool):
        self.is_available= value
    def set_is_holiday(self,value:bool):
        self.is_holiday= value

class DutyScheduleTable():

    def __init__(
            self,
            num_gps:int,
            num_days:int,
            first_day_index:int,
            holiday_dates:list,
            all_wards:list,
            gp_alloc_per_ward:int,
            free_days_after_duty:int = 1
        ):
        super().__init__()
        self._days_of_week=['mon','tue','wed','thr','fri','sat','sun']
        self.data = {}
        self.fn_unattainables=[]
        self.fn_added_rules=[]
        self.fn_basic_rules=[]
        self.fn_optimizers=[]
        self.fn_display_results=[]
        self.num_gps= num_gps
        self.num_days= num_days
        self.first_day_index= first_day_index
        self.holiday_dates_indexes=self.map_dates_to_indexes(holiday_dates)
        self.all_wards = all_wards
        self.gp_alloc_per_ward = gp_alloc_per_ward
        self.free_days_after_duty = free_days_after_duty
        self.prev_duty = {}
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.make_schedule_table()

    def get_model(self):
        return self.model
    def make_schedule_table(self):
        for gp in range(self.num_gps):
            for d in range(self.num_days):
                for w in self.all_wards:
                    for t in range(self.gp_alloc_per_ward):
                        self.data[(gp,d,w,t)]= AtomicScheduleData(self.model.new_bool_var(f"shift_gp{gp}_d{d}_w{w}_t{t}"))
                        if self.is_weekend(d):
                            self.data.get((gp,d,w,t)).set_is_weekend(True)
                        if d in self.holiday_dates_indexes:
                            self.data.get((gp,d,w,t)).set_is_holiday(True)
    def get_day_of_week(self,d):
        # change_k = 7 - len(prev_duty_shift) if len(prev_duty_shift)<=7 else 7 - (len(prev_duty_shift)%7)
        return int(d+self.first_day_index)%(len(self._days_of_week)) if (d+self.first_day_index)>=len(self._days_of_week) else int(d+self.first_day_index)
    #check if the date is weekend
    def is_weekend(self,d):
        dow = self.get_day_of_week(d)
        return True if dow in (5,6) else False
        
    def map_dates_to_indexes(self,ds:list)->list:
        return list(map(lambda d : d-1 if d-1>=0 else 0, ds))
    def is_d_holiday(self,d,use_direct=True):
        if not use_direct:
            d = d-1 if d-1>=0 else 0
        if d in self.holiday_dates_indexes: return True
        else: return False
    
    #is the cell available
    def is_cell_available(self,gp,d,w,t)->bool:
        if self.data.get((gp,d,w,t),None):
            return self.data.get((gp,d,w,t)).get_is_available()
        return False
    # is the celll an entry
    def is_cell_entry(self,gp,d,w,t)->bool:
        if self.is_cell_available(gp,d,w,t) and self.get_data(gp,d,w,t) :
            return self.get_data(gp,d,w,t).get_is_entry()
        return False
    # is the cell an weekend
    def is_cell_weekend(self,gp,d,w,t)->bool:
        if self.is_cell_available(gp,d,w,t) and self.get_data(gp,d,w,t) :
            return self.get_data(gp,d,w,t).get_is_weekend()
        return False
    # is the cell a holida
    def is_cell_holiday(self,gp,d,w,t)->bool:
        if self.is_cell_available(gp,d,w,t) and self.get_data(gp,d,w,t) :
            return self.get_data(gp,d,w,t).get_is_holiday()
        return False
    # is the cell requested valid and found in data
    def is_data_available(self,gp,d,w,t):
        if self.data.get((gp,d,w,t),None):
            return True
        return False
    # get AtomicScheduleData object
    def get_data(self,gp,d,w,t)->AtomicScheduleData:
        if self.is_data_available(gp,d,w,t):
            return self.data.get((gp,d,w,t))
        return None
    # get the value from the AtomicScheduleData object stored in data 
    def get_cell_value(self,gp,d,w,t,default=None):
        if self.get_data(gp,d,w,t):
            return self.get_data(gp,d,w,t).get_value()
        return default
    # get the value from the AtomicScheduleData object stored in data if available 
    def get_available_cell_value(self,gp,d,w,t,default=None):
        if self.get_data(gp,d,w,t) and self.is_cell_available(gp,d,w,t):
            return self.get_data(gp,d,w,t).get_value()
        return default
    def get_available_entry_cell_value(self,gp,d,w,t,default=None):
        if self.get_data(gp,d,w,t) and self.is_cell_available(gp,d,w,t) and self.is_cell_entry(gp,d,w,t):
            return self.get_data(gp,d,w,t).get_value()
        return default
    
    def rule_make_one_gp_per_cell(self):
        for d in range(self.num_days):
            for w in self.all_wards:
                for t in range(self.gp_alloc_per_ward):
                    gps_per_cell = list(self.get_cell_value(gp,d,w,t,0) for gp in range(self.num_gps) if self.is_cell_available(gp,d,w,t))
                    if len(gps_per_cell):
                        self.model.add_exactly_one(gps_per_cell)

    def rule_make_one_gp_per_day(self):
        for gp in range(self.num_gps):
            for d in range(self.num_days):
                self.model.add_at_most_one(self.get_available_cell_value(gp,d,w,t,0) for w in self.all_wards for t in range(self.gp_alloc_per_ward))

    def add_on_prev_duty(self,prev_index,list_gps:list):
        #prev_index is in negative; counted backward from the first day of duty as zero
        if prev_index >=0: return ValueError()
        self.prev_duty.setdefault((prev_index),[]).extend(list_gps)
    def get_on_prev_duty(self,prev_index):
        return self.prev_duty.get((prev_index),None)
    def clear_on_prev_duty(self,prev_index):
        return self.prev_duty.pop(prev_index,None)
    def clear_all_prev_duty(self):
        self.prev_duty.clear()
    #skip duty based on prev shift index
    def skip_duty_based_on_prev_index(self,prev_duty_index,freedays_after_duty,gp):
        print("skip prev run",[gp])
        i=0
        j=prev_duty_index + freedays_after_duty
        if j<0:
            return
        else:
            self.skip_duty(gp,[d for d in range(i,j+1)],True)
    #rule for skipping duty on based on the previous duty entry
    def rule_skip_prev_duty(self,free_days_after_duty):
        for (prev_index), list_gps in self.prev_duty.items():
            for gp in list_gps:
                self.skip_duty_based_on_prev_index(prev_index,free_days_after_duty,gp) 
    #Free days after duty inside the table
    def rule_force_free_after_duty(self,free_days_after_duty:int,gps:list=[], ds:list=[]):
        ds = DutyScheduleTable.empty_defaulter(ds,[d for d in range(self.num_days)])
        gps = DutyScheduleTable.empty_defaulter(gps,[gp for gp in range(self.num_gps)])
        for gp in gps:
            for d in ds:
                self.force_free_after_duty(free_days_after_duty,d,gp)
    def force_free_after_duty(self,freedays_after_duty,d,gp):
        i = d
        j = d+freedays_after_duty+1 if d+freedays_after_duty+1<self.num_days else self.num_days
        # self.skip_duty(gp,[d for d in range(i,j)],True)
        self.model.add_at_most_one((self.get_available_cell_value(gp,dd,ww,tt,0) for dd in range(i,j) for ww in self.all_wards for tt in range(self.gp_alloc_per_ward) if self.is_cell_entry(gp,dd,ww,tt)))
        # self.model.add(sum(self.get_available_cell_value(gp,dd,ww,tt,0) for dd in range(i,j) for ww in self.all_wards for tt in range(self.gp_alloc_per_ward) if self.is_cell_entry(gp,dd,w,t))<=1)
    def empty_defaulter(ls:list,default):
        return ls if ls and ls.__len__ else default
    #way to make is_available (off) based on d, w,t
    def set_cells_unavailable(self,unav_ds:list=[],unav_ws:list=[],unav_ts:list=[]):
        unav_ds=DutyScheduleTable.empty_defaulter(unav_ds,[d for d in range(self.num_days)])
        unav_ws=DutyScheduleTable.empty_defaulter(unav_ws,[w for w in self.all_wards])
        unav_ts=DutyScheduleTable.empty_defaulter(unav_ts,[t for t in range(self.gp_alloc_per_ward)])
        unavailable_gen = (self.get_data(gp,d,w,t) for gp in range(self.num_gps) for d in unav_ds for w in unav_ws for t in unav_ts)
        # map(lambda d : d.set_is_available(False),unavailable_gen)
        for unav_data in unavailable_gen:
            unav_data.set_is_available(False)
        self.model.add(sum(self.get_cell_value(gp,d,w,t,0) for gp in range(self.num_gps) for d in unav_ds for w in unav_ws for t in unav_ts if not self.is_cell_available(gp,d,w,t))==0)
    #way to make is_available (off) based on d, w,t
    def set_cells_unentry(self,unentry_ds:list=[],unentry_ws:list=[],unentry_ts:list=[]):
        unentry_ds=DutyScheduleTable.empty_defaulter(unentry_ds,[d for d in range(self.num_days)])
        unentry_ws=DutyScheduleTable.empty_defaulter(unentry_ws,[w for w in self.all_wards])
        unentry_ts=DutyScheduleTable.empty_defaulter(unentry_ts,[t for t in range(self.gp_alloc_per_ward)])
        unentry_gen = (self.get_data(gp,d,w,t) for gp in range(self.num_gps) for d in unentry_ds for w in unentry_ws for t in unentry_ts)
        # map(lambda d : d.set_is_available(False),unentry_gen)
        for unentry_data in unentry_gen:
            unentry_data.set_is_entry(False)

    #skip_duty whether is entry or not
    def skip_duty_all(self,sgp:int,sds:list[int],use_sds_direct=False):
        if not use_sds_direct:
            sds = list(map(lambda d:d-1,sds))
        skip_gen = (self.get_available_cell_value(sgp,d,w,t,0) for d in sds for w in self.all_wards for t in range(self.gp_alloc_per_ward)) 
        self.model.add(sum(skip_gen)==0)
    #can't_be_on_duty function
    def skip_duty(self,sgp:int,sds:list[int],use_sds_direct=False):
        if not use_sds_direct:
            sds = list(map(lambda d:d-1,sds))
        skip_gen = (self.get_available_entry_cell_value(sgp,d,w,t,0) for d in sds for w in self.all_wards for t in range(self.gp_alloc_per_ward))
        self.model.add(sum(skip_gen)==0)
    #must be on duty function
    def entry_duty(self,egp:int,eds:list[int],use_eds_direct=False):
        if not use_eds_direct:
            eds = list(map(lambda d:d-1,eds))
        for d in eds:
            entry_gen = (self.get_available_entry_cell_value(egp,d,w,t,0) for w in self.all_wards for t in range(self.gp_alloc_per_ward) )
            self.model.add(sum(entry_gen)==1)
            # model.add_exactly_one(sgp_values)
    #count how many time each gp got into duty together
    def count_them_if_together(self,gpx,gpy,weekend_exc = False,ws=[],ds=[],ts=[]):
        list_gp_x_y_together=[]
        ds=DutyScheduleTable.empty_defaulter(ds,[d for d in range(self.num_days)])
        ws=DutyScheduleTable.empty_defaulter(ws,[w for w in self.all_wards])
        ts=DutyScheduleTable.empty_defaulter(ts,[t for t in range(self.gp_alloc_per_ward)])
        for d in ds:
            if weekend_exc and (self.get_day_of_week(d) in [5,6]):
                continue
            has_gpx_enter = self.get_model().new_bool_var(f"has_{gpx}_on{d}")
            has_gpy_enter = self.get_model().new_bool_var(f"has_{gpy}_on{d}")
            self.get_model().add_max_equality(has_gpx_enter,[self.get_available_entry_cell_value(gpx,d,w,t,0) for w in ws for t in ts])
            self.get_model().add_max_equality(has_gpy_enter,[self.get_available_entry_cell_value(gpy,d,w,t,0) for w in ws for t in ts])
            mark_d = self.get_model().new_bool_var(f"mark_{d}_{gpx}_{gpy}")
            # if i == 1245:
            #     print(has_gpy_enter.Index()," y",i,d)
            #     print(has_gpx_enter.Index()," x",i,d)
            #     print(mark_d.Index()," md",i,d)
            self.get_model().add_bool_and([has_gpy_enter,has_gpx_enter]).only_enforce_if(mark_d)
            self.get_model().add_bool_or([has_gpy_enter.Not(),has_gpx_enter.Not()]).only_enforce_if(mark_d.Not())
            list_gp_x_y_together.append(mark_d)
        count_gp_x_y_together = self.get_model().new_int_var(0,self.num_days,f"count_gp_{gpx}_{gpy}_together")
        self.get_model().add(count_gp_x_y_together==sum(list_gp_x_y_together))
        return count_gp_x_y_together
    #how many duty entries
    def count_entry_for_gp(self,gp,ws=[],ds=[],ts=[]):
        ds=DutyScheduleTable.empty_defaulter(ds,[d for d in range(self.num_days)])
        ws=DutyScheduleTable.empty_defaulter(ws,[w for w in self.all_wards])
        ts=DutyScheduleTable.empty_defaulter(ts,[t for t in range(self.gp_alloc_per_ward)])
        count_gp_entry = self.get_model().new_int_var(0,self.num_days,f'count_entry_{gp}')
        self.get_model().add(count_gp_entry==sum(self.get_available_entry_cell_value(gp,d,w,t,0) for d in ds for w in ws for t in ts))
        return count_gp_entry

    def run_solver(self,max_min):
        self.get_model().add_decision_strategy( #best decision strategy to do for scheduling
        [self.get_cell_value(gp,d,w,t,0) 
         for gp in range(self.num_gps) for d in range(self.num_days) for w in self.all_wards for t in range(self.gp_alloc_per_ward)
         if self.is_cell_available(gp,d,w,t) and self.is_data_available(gp,d,w,t)
        ],
        cp_model.CHOOSE_LOWEST_MIN,
        cp_model.SELECT_MIN_VALUE
        )
        self.solver.parameters.max_time_in_seconds= 60*max_min
        self.solver.parameters.log_search_progress = True
        #default and randomize
        self.solver.parameters.random_seed = 48
        self.solver.parameters.randomize_search = True
        # self.solver.parameters.search_random_variable_pool_size = 30
        # self.solver.parameters.use_overload_checker_in_cumulative = False
        self.solver.parameters.add_clique_cuts = True
        self.solver.parameters.add_objective_cut = True
        #make the search aggressive
        # self.solver.parameters.search_branching = cp_model.FIXED_SEARCH
        self.solver.parameters.use_sat_inprocessing = True
        self.solver.parameters.use_objective_lb_search = True
        self.solver.parameters.use_feasibility_pump = True
        self.solver.parameters.use_feasibility_jump = True
        self.solver.parameters.use_extended_probing = True
        self.solver.parameters.use_blocking_restart = True
        self.solver.parameters.use_objective_shaving_search = True
        #self.solver performance
        #self.solver.parameters.num_search_workers = 4 
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.cp_model_probing_level = 2 #agrresive assignment and pruning done on presolve
        self.solver.parameters.optimize_with_core= True #uses unsat to prune out imposible bounds on presolve
        self.solver.parameters.optimize_with_max_hs = True #works with optimize_with_core increase effeciency
        # self.solver.parameters.optimize_with_lb_tree_search = True #experimental; don't use it #tree based lower bound chasing to prune it if lower than current best
        self.solver.parameters.linearization_level = 3 #high optimazation required for multiple boolvar and intvar
        self.solver.parameters.use_lns = True #LNS (large neighberhood search)
        self.solver.parameters.use_lns_only = False
        self.solver.parameters.use_lb_relax_lns = True #fancy lns 
        self.solver.parameters.use_rins_lns = True
        # self.solver.parameters.polish_lp_solution = True
        self.solver.parameters.use_dual_scheduling_heuristics = True
        # callback = Solution_Callback(self.solver,stop_event)
        status = self.solver.solve(self.model)
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return self.gp_result_per_days(self.gp_result_for_cells())
        elif status != cp_model.FEASIBLE:
            print("Not Feasible")
            return None

    #to store the selected gp for each specified duty
    def gp_result_for_cells(self):
        gp_result ={}
        for d in range(self.num_days):
            for w in self.all_wards:
                for t in range(self.gp_alloc_per_ward):
                    for gp in range(self.num_gps):
                        if self.solver.value(self.get_available_cell_value(gp,d,w,t,0))==1:
                            gp_result[(d,w,t)]=gp
                            # gp_result.setdefault((d,w,t),[]).append(gp)
        return gp_result
    #to store the selected gp based on date then (w,t)
    def gp_result_per_days(self,gp_result:dict):
        gp_result_as_per_day={}
        for (d,w,t),gp in gp_result.items():
            each_day:dict = gp_result_as_per_day.setdefault(d,{})
            each_day.setdefault((w,t),gp)
        return gp_result_as_per_day
    def create_csv_ward_based(self,gp_result_per_day:dict,filename:str='duty_csv.csv'):
        with open(filename,'w',newline='') as f:
            ward_types = [f"{w}" for w in self.all_wards]
            fieldnames = ['date']
            fieldnames.extend(ward_types)
            writer = csv.DictWriter(f,fieldnames=fieldnames)
            for d, dict_each_day in gp_result_per_day.items():
                #for each day
                rows_alloc_for_ward = {}
                for (w,t), gp in dict_each_day.items():
                    each_row:dict = rows_alloc_for_ward.setdefault(t,{})
                    each_row.setdefault(w,gp)
                    if t == 0: each_row.setdefault('date',d)
                writer.writerows(rows_alloc_for_ward.values())

    #helper function: to put similar object function in a list
    def fn_adder_to_list(fn_lists:list,fn_callback,*args, **kwargs):
        fn_lists.append({
            "fn_callback":fn_callback,
            "args":args,
            "kwargs":kwargs
        })
    #helper function: call the object function
    def fn_caller(fn):
        fn["fn_callback"](*fn["args"], **fn["kwargs"])
    
    def run_basic_rules(self):
        self.rule_make_one_gp_per_cell()
        self.rule_make_one_gp_per_day() #can modified later if necessary
        # self.rule_force_free_after_duty(self.free_days_after_duty)
        for fn in self.fn_basic_rules:
            DutyScheduleTable.fn_caller(fn)
        # self.rule_skip_prev_duty(self.free_days_after_duty)
    def add_on_basic_rules(self,fn_callback,*args, **kwargs):
        DutyScheduleTable.fn_adder_to_list(self.fn_basic_rules,fn_callback,*args, **kwargs)


    def run_unattainable(self):
        print("unattainable_run")
        for fn in self.fn_unattainables:
            DutyScheduleTable.fn_caller(fn)
    def add_on_unattainable(self,fn_callback,*args, **kwargs):
        DutyScheduleTable.fn_adder_to_list(self.fn_unattainables,fn_callback,*args, **kwargs)
    

    def run_added_rules(self):
        print("added_rule_run")
        for fn in self.fn_added_rules:
            DutyScheduleTable.fn_caller(fn)
    def add_on_added_rules(self,fn_callback,*args, **kwargs):
        DutyScheduleTable.fn_adder_to_list(self.fn_added_rules,fn_callback,*args, **kwargs)

    def run_optimizers(self):
        print("optimizer run")
        for fn in self.fn_optimizers:
            DutyScheduleTable.fn_caller(fn)
    def add_on_optimizers(self,fn_callback,*args, **kwargs):
        DutyScheduleTable.fn_adder_to_list(self.fn_optimizers,fn_callback,*args, **kwargs)

    def display_result(self):
        print("Done")
        for fn in self.fn_display_results:
            DutyScheduleTable.fn_caller(fn)
    def add_on_display_results(self,fn_callback,*args, **kwargs):
        DutyScheduleTable.fn_adder_to_list(self.fn_display_results,fn_callback,*args, **kwargs)
    def run_all(self,max_min):
        self.run_unattainable() #first run, to eliminate unavailable cells
        self.run_basic_rules() #basic rules that make scheduling
        self.run_added_rules() #program specific rules
        self.run_optimizers() #optimization
        result = self.run_solver(max_min)
        if result:
            self.display_result()
        return result

class AlertDutyScheduler(DutyScheduleTable):
    class Hr_mng():
        def __init__(self,hr:int,mul:float,name='') -> None:
            self.hr = hr
            self.mul = mul 
            self.name = name
        def get_hr(self):
            return self.hr
        def get_mul(self):
            return self.mul
        def get_mul_hr(self):
            return self.hr * self.mul
        def cal_adjuster(self):
            mul_str = str(self.mul)
            i = mul_str[::-1].find('.')
            if i == -1:
                return 1
            else:
                return 10**i
    def __init__(self, num_gps: int, num_days: int, first_day_index: int, holiday_dates: list, all_wards: list, gp_alloc_per_ward: int):
        super().__init__(num_gps, num_days, first_day_index, holiday_dates, all_wards, gp_alloc_per_ward)
        self.hr_managment={
            'hol_day':AlertDutyScheduler.Hr_mng(24,2.5,'hol_day'),
            'mon-thr':AlertDutyScheduler.Hr_mng(16,1.5,'mon_thr'),
            'fri':AlertDutyScheduler.Hr_mng(17,1.5,'fri'),
            'sat-sun':AlertDutyScheduler.Hr_mng(24,2,'sat_sun'),
            'ART': AlertDutyScheduler.Hr_mng(8,2,'ART'),
        }
        self.adjuster = max((hrmn.cal_adjuster() for hrmn in self.hr_managment.values()))
        self.max_mul = int(max((hrmn.get_mul_hr() for hrmn in self.hr_managment.values())))
        self.special_ward = ['ART']
        self.not_eff_gps = []
        self.extra_eff_gps = []
        self.weighted_values_for_optimization = []
        self.displayable_values=[]
        self.displayable_per_gp_value_dict=[]
        self.add_on_optimizers(self.hr_optimization)
        self.add_on_optimizers(self.weekend_hol_num_opt)
        self.add_on_display_results(self.display_opt_res)
        self.add_on_display_results(self.display_opt_per_gp)
        self.add_on_display_results(self.display_opt_values)
    #set non effective gps
    def add_not_eff_gps(self,gps:list):
        self.not_eff_gps.extend(gps)
    def add_extra_eff_gps(self,gps:list):
        self.extra_eff_gps.extend(gps)

    def get_eff_gps(self):
        return [gp for gp in range(self.num_gps) if not (gp in self.not_eff_gps) and not(gp in self.extra_eff_gps)]
    def get_extra_eff_gps(self):
        return self.extra_eff_gps
    
    def add_displayable_values(self,vs:list):
        self.displayable_values.extend(vs)
    def add_displayable_per_gp_value_dict(self,vs:list):
        self.displayable_per_gp_value_dict.extend(vs)
    def display_opt_res(self):
        #to show per gp result 
        self.add_displayable_per_gp_value_dict([self.cal_gp_hr,self.cal_gp_mul_hr,self.cal_gp_entry_hr,self.cal_gp_weekend_hol_num])
        #to show the general max and min results
        self.add_displayable_values([
            self.max_hr,self.min_hr,
            self.max_mul_hr,self.min_mul_hr,
            self.max_entry_hr,self.min_entry_hr,
            self.max_weekend_hol_num,self.min_weekend_hol_num,
            ])
    def str_sol_value(self,var:cp_model.IntVar):
        return f' {var.name}={self.solver.value(var)} '
    def str_sol_value_per_gp(self,cal_per_gp_var:dict,gp:int):
        if not(gp in cal_per_gp_var.keys()): return ' '
        var:cp_model.IntVar = cal_per_gp_var.get(gp)
        return f' {var.name}={self.solver.value(var)} '
    def sum_sol_value_for_list(self,value_list:list):
        sol_value_list=[]
        for value_to_be_sol in value_list:
            sol_value_list.append(self.solver.value(value_to_be_sol))
        return sum(sol_value_list)
    def display_opt_per_gp(self):
        for gp in range(self.num_gps):
            display_text = f' gp_{gp} :'
            for displayable_value_dict in self.displayable_per_gp_value_dict:
                display_text = display_text + self.str_sol_value_per_gp(displayable_value_dict,gp)
            print(display_text)
    def display_opt_values(self):
        display_text = ''
        for displayable_value in self.displayable_values:
            display_text = display_text + self.str_sol_value(displayable_value)
        print(display_text)
    #minimization function
    def use_minimize_model(self):
        self.get_model().minimize(sum(self.weighted_values_for_optimization))
    def hr_opt_gen_hr(self):
        self.max_hr, self.min_hr, self.cal_gp_hr = self.max_min_opt_per_gp_helper('hr',24*self.num_days,self.opt_hr_diff_logic)
        self.max_mul_hr, self.min_mul_hr, self.cal_gp_mul_hr = self.max_min_opt_per_gp_helper('mul_hr',self.max_mul*self.num_days*self.adjuster,self.opt_mul_hr_diff_logic)
        self.max_entry_hr, self.min_entry_hr, self.cal_gp_entry_hr = self.max_min_opt_per_gp_helper('entry_hr',24*self.num_days,self.opt_entry_hr_diff_logic)
        self.add_on_diff_weighted_values(self.max_mul_hr,self.min_mul_hr,4,False) #add it to list for sumation which will be minimized
        # self.add_on_diff_weighted_values(self.max_hr,self.min_hr,2)
        self.add_on_diff_weighted_values(self.max_hr,self.min_hr,2)
        self.add_on_diff_weighted_values(self.max_entry_hr,self.min_entry_hr,2)
    def hr_opt_eff_hr(self):
        if len(self.not_eff_gps)==0: return
        self.max_eff_hr, self.min_eff_hr, self.cal_gp_eff_hr = self.max_min_opt_per_gp_helper('eff_hr',24*self.num_days,self.opt_hr_diff_logic,gps=self.get_eff_gps())
        self.max_mul_eff_hr, self.min_mul_eff_hr, self.cal_gp_mul_eff_hr = self.max_min_opt_per_gp_helper('mul_eff_hr',self.max_mul*self.num_days*self.adjuster,self.opt_mul_hr_diff_logic,gps=self.get_eff_gps())
        self.max_entry_eff_hr, self.min_entry_eff_hr, self.cal_gp_entry_eff_hr = self.max_min_opt_per_gp_helper('entry_eff_hr',24*self.num_days,self.opt_entry_hr_diff_logic,gps=self.get_eff_gps())
        self.add_on_diff_weighted_values(self.max_mul_eff_hr,self.min_mul_eff_hr,8,False) #add it to list for sumation which will be minimized
        self.add_on_diff_weighted_values(self.max_eff_hr,self.min_eff_hr,4)
        self.add_on_diff_weighted_values(self.max_entry_eff_hr,self.min_entry_eff_hr,4)
        self.get_model().add(self.min_eff_hr >= self.min_hr)
        self.get_model().add(self.min_mul_eff_hr >= self.min_mul_hr)
        self.get_model().add(self.min_entry_eff_hr >= self.min_entry_eff_hr)
        self.add_displayable_values([
            self.max_eff_hr,self.min_eff_hr,
            self.max_mul_eff_hr,self.min_mul_eff_hr,
            self.max_entry_eff_hr,self.min_entry_eff_hr,
            ])

    def hr_opt_extra_eff_hr(self):
        if len(self.extra_eff_gps)==0:return
        self.max_extra_eff_hr, self.min_extra_eff_hr, self.cal_gp_extra_eff_hr = self.max_min_opt_per_gp_helper('extra_eff_hr',24*self.num_days,self.opt_hr_diff_logic,gps=self.get_extra_eff_gps())
        self.max_mul_extra_eff_hr, self.min_mul_extra_eff_hr, self.cal_gp_mul_extra_eff_hr = self.max_min_opt_per_gp_helper('mul_extra_eff_hr',self.max_mul*self.num_days*self.adjuster,self.opt_mul_hr_diff_logic,gps=self.get_extra_eff_gps())
        self.max_entry_extra_eff_hr, self.min_entry_extra_eff_hr, self.cal_gp_entry_extra_eff_hr = self.max_min_opt_per_gp_helper('entry_extra_eff_hr',24*self.num_days,self.opt_entry_hr_diff_logic,gps=self.get_extra_eff_gps())
        self.add_on_diff_weighted_values(self.max_mul_extra_eff_hr,self.min_mul_extra_eff_hr,8,False) #add it to list for sumation which will be minimized
        self.add_on_diff_weighted_values(self.max_extra_eff_hr,self.min_extra_eff_hr,4)
        self.add_on_diff_weighted_values(self.max_entry_extra_eff_hr,self.min_entry_extra_eff_hr,4)
        self.get_model().add(self.min_mul_extra_eff_hr > self.min_mul_eff_hr)
        self.get_model().add(self.min_extra_eff_hr > self.min_eff_hr)
        self.get_model().add(self.min_entry_extra_eff_hr > self.min_entry_eff_hr)
        self.add_displayable_values([
            self.max_extra_eff_hr,self.min_extra_eff_hr,
            self.max_mul_extra_eff_hr,self.min_mul_extra_eff_hr,
            self.max_entry_extra_eff_hr,self.min_entry_extra_eff_hr,
            ])
    def weekend_hol_num_opt(self):
        self.max_weekend_hol_num,self.min_weekend_hol_num,self.cal_gp_weekend_hol_num = self.max_min_opt_per_gp_helper('weekend_hol_num',self.num_days,self.opt_num_weekend_holiday_logic)
        self.max_weekend_hol_hr,self.min_weekend_hol_hr,self.cal_gp_weekend_hol_hr = self.max_min_opt_per_gp_helper('weekend_hol_num',24*self.num_days,self.opt_hr_weekend_holiday_logic)
        self.add_on_diff_weighted_values(self.max_weekend_hol_num,self.min_weekend_hol_num,4)
        self.add_on_diff_weighted_values(self.max_weekend_hol_hr,self.min_weekend_hol_hr,2)
        
    #hour optimization (in this case, minimization) 
    def hr_optimization(self):
        self.hr_opt_gen_hr()
        self.hr_opt_eff_hr()
        self.hr_opt_extra_eff_hr()
        # self.get_model().minimize(
        #     2*(self.max_hr-self.min_hr)*self.adjuster
        #     +4*(self.max_mul_hr-self.min_mul_hr)
        #     +2*(self.max_entry_hr-self.min_entry_hr)*self.adjuster
        # )
    def add_on_weighted_values(self,expression,weight,use_adjuster:bool = True): #create an expression with weight to be minimized
        if use_adjuster:
            weight = int(weight*self.adjuster)
        self.weighted_values_for_optimization.append(weight*expression)
    def add_on_diff_weighted_values(self,max:cp_model.IntVar,min:cp_model.IntVar,weight,use_adjuster:bool=True):
        self.add_on_weighted_values(max-min,weight,use_adjuster)
        # self.add_on_weighted_values(max,weight,use_adjuster)
        # self.add_on_weighted_values(min,-1*weight,use_adjuster)
    
    
    def opt_hr_weekend_holiday_logic(self,gp,cal_weekend_hol_hr):
        weekend_hol_per_gp = (self.get_available_entry_cell_value(gp,d,w,t,0)*self.cal_hrs_per_hr_management(self.get_data(gp,d,w,t),d,w).get('hr',0) for d in range(self.num_days) for w in self.all_wards for t in range(self.gp_alloc_per_ward) if self.is_cell_weekend(gp,d,w,t) or self.is_cell_holiday(gp,d,w,t))
        self.get_model().add(cal_weekend_hol_hr==sum(weekend_hol_per_gp))
    def opt_num_weekend_holiday_logic(self,gp,cal_weekend_hol_num):
        weekend_hol_per_gp = (self.get_available_entry_cell_value(gp,d,w,t,0) for d in range(self.num_days) for w in self.all_wards for t in range(self.gp_alloc_per_ward) if self.is_cell_weekend(gp,d,w,t) or self.is_cell_holiday(gp,d,w,t))
        self.get_model().add(cal_weekend_hol_num==sum(weekend_hol_per_gp))
    def opt_hr_diff_logic(self,gp,cal_list_per_gp):
        gp_hrs_data_set = self.hr_calculator_per_gp(gp)
        self.get_model().add(cal_list_per_gp==sum(gp_hrs_data_set['hr']))
    def opt_mul_hr_diff_logic(self,gp,expected_mul_hr):
        gp_hrs_data_set = self.hr_calculator_per_gp(gp)
        self.get_model().add(expected_mul_hr==sum(gp_hrs_data_set['mul_hr']))
    def opt_entry_hr_diff_logic(self,gp,expected_entry_hr):
        gp_hrs_data_set = self.hr_calculator_per_gp(gp)
        self.get_model().add(expected_entry_hr==sum(gp_hrs_data_set['entry_hr']))
    def max_min_opt_per_gp_helper(self,name,max_val,logic,min_val=0,gps=[]):
        gps = DutyScheduleTable.empty_defaulter(gps,[gp for gp in range(self.num_gps)])
        cal_list={}
        max = self.get_model().new_int_var(min_val,max_val,f'max_{name}')
        min = self.get_model().new_int_var(min_val,max_val,f'min_{name}')
        self.get_model().add(max>=min)
        for gp in gps:
            cal_list[gp] = self.get_model().new_int_var(0,max_val,f'cal_{name}_{gp}')
            self.get_model().add(cal_list[gp]<=max)
            self.get_model().add(cal_list[gp]>=min)
            logic(gp,cal_list[gp])
        return (max, min, cal_list)
    def hr_calculator_per_gp(self,gp:int,ds:list=[],ws:list=[],ts:list=[]):
        cal_gp_hrs_data_set={'hr':[],'mul_hr':[],'entry_hr':[]}
        ds = DutyScheduleTable.empty_defaulter(ds,[d for d in range(self.num_days)])
        ws = DutyScheduleTable.empty_defaulter(ws,[w for w in self.all_wards])
        ts = DutyScheduleTable.empty_defaulter(ts,[t for t in range(self.gp_alloc_per_ward)])
        cal_gp_hrs_data_set['hr']=(self.get_available_cell_value(gp,d,w,t,0)*self.cal_hrs_per_hr_management(self.get_data(gp,d,w,t),d,w).get('hr',0) for d in ds for w in ws for t in ts)
        cal_gp_hrs_data_set['mul_hr']=(self.get_available_cell_value(gp,d,w,t,0)*self.cal_hrs_per_hr_management(self.get_data(gp,d,w,t),d,w).get('mul_hr',0) for d in ds for w in ws for t in ts)
        cal_gp_hrs_data_set['entry_hr']=(self.get_available_cell_value(gp,d,w,t,0)*self.cal_hrs_per_hr_management(self.get_data(gp,d,w,t),d,w).get('entry_hr',0) for d in ds for w in ws for t in ts)
        return cal_gp_hrs_data_set
        
    def cal_hrs_per_hr_management(self,cell_data:AtomicScheduleData,d:int,w:str=''):
        def cal_hrs_val(hm:AlertDutyScheduler.Hr_mng):
            hrs_val = {'hr':0,'mul_hr':0,'entry_hr':0}
            hrs_val['hr']=hm.get_hr()
            hrs_val['mul_hr']=int(hm.get_mul_hr()*self.adjuster)
            if cell_data.get_is_entry():
                hrs_val['entry_hr']=hm.get_hr()
            return hrs_val
        if w == 'ART':
            hm = self.hr_managment.get('ART')
        elif cell_data.get_is_holiday():
            hm = self.hr_managment.get('hol_day')
        else:
            if self.is_friday(d): #on friday
                hm = self.hr_managment.get('fri')
            elif self.is_weekend(d):
                hm = self.hr_managment.get('sat-sun')
            else:
                hm = self.hr_managment.get('mon-thr')
        return cal_hrs_val(hm)
    def is_friday(self,d):
        return True if self.get_day_of_week(d)==4 else False
    
    def show_value(self,value,name=''):
        print(f'{name} = {value}')
    def show_sum_values_after_solve(self,list_values:list,name=''):
        result = self.sum_sol_value_for_list(list_values)
        self.show_value(result,name)
    def make_two_gps_apart(self,list_gps:list=[],ws:list=[],ds:list=[],ts:list=[],count_spec:bool=False,count_spec_range:tuple=(0,0)):
        count_together=[]
        for (gpx,gpy) in list_gps:
            count_together.append(self.count_them_if_together(gpx,gpy,ws=ws,ds=ds,ts=ts))
        if count_spec:
            self.get_model().add(sum(count_together)>=count_spec_range[0])
            self.get_model().add(sum(count_together)<=count_spec_range[1])
        self.add_on_weighted_values(sum(count_together),2)
        self.add_on_display_results(self.show_sum_values_after_solve,count_together,'sum_for_apart')
    def make_two_gps_together(self,list_gps:list=[],ws:list=[],ds:list=[],ts:list=[],mode='r',count_spec:bool=False,count_spec_range:tuple=(0,0)):
        for (gpx,gpy) in list_gps:
            count_together = self.count_them_if_together(gpx,gpy,ws=ws,ds=ds,ts=ts)
            count_gpx=self.count_entry_for_gp(gpx,ws=ws,ds=ds,ts=ts)
            count_gpy=self.count_entry_for_gp(gpy,ws=ws,ds=ds,ts=ts)
            if mode.strip().lower() == 'r':
                self.add_on_diff_weighted_values(count_gpx,count_together,6)
            elif mode.strip().lower() == 'l':
                self.add_on_diff_weighted_values(count_gpy,count_together,6)
            elif mode.strip().lower() == 'b':
                self.add_on_weighted_values(count_gpx+count_gpy-(2*count_together),6)
            if count_spec:
                self.get_model().add(count_together>=count_spec_range[0])
                self.get_model().add(count_together<=count_spec_range[1])
                
            self.add_on_display_results(self.show_sum_values_after_solve,[count_together],f'sum_for_together_{gpx}_{gpy}')
            self.add_displayable_values([count_together,count_gpx,count_gpy])
    def check_hrs_values(self,gp_result_per_day:dict,create_csv:bool=False):
        checked_gp_hrs={}
        checked_gp_hrs_initial_state={
            'hr':0,'mul_hr':0,
            'mon-thr':0,'fri':0,'sat-sun':0,'ART':0,'hol_day':0,
            'cal_hr':0,'cal_mul_hr':0
        }
        for d, each_day_dict in gp_result_per_day.items():
            for (w,t),gp in each_day_dict.items():
                gp_hr_value = checked_gp_hrs.setdefault(gp,checked_gp_hrs_initial_state.copy())
                if w == 'ART':
                    hm = self.hr_managment.get('ART')
                    gp_hr_value['ART'] = gp_hr_value['ART']+1
                    gp_hr_value['cal_hr']=gp_hr_value['cal_hr']+ hm.get_hr()
                    gp_hr_value['cal_mul_hr']=gp_hr_value['cal_mul_hr']+ hm.get_mul_hr()
                elif self.is_d_holiday(d):
                    hm = self.hr_managment.get('hol_day')
                    gp_hr_value['hol_day'] = gp_hr_value['hol_day']+1
                    gp_hr_value['cal_hr']=gp_hr_value['cal_hr']+ hm.get_hr()
                    gp_hr_value['cal_mul_hr']=gp_hr_value['cal_mul_hr']+ hm.get_mul_hr()
                else:
                    if self.is_friday(d): #on friday
                        hm = self.hr_managment.get('fri')
                        gp_hr_value['fri'] = gp_hr_value['fri']+1
                        gp_hr_value['cal_hr']=gp_hr_value['cal_hr']+ hm.get_hr()
                        gp_hr_value['cal_mul_hr']=gp_hr_value['cal_mul_hr']+ hm.get_mul_hr()
                    elif self.is_weekend(d):
                        hm = self.hr_managment.get('sat-sun')
                        gp_hr_value['sat-sun'] = gp_hr_value['sat-sun']+1
                        gp_hr_value['cal_hr']=gp_hr_value['cal_hr']+ hm.get_hr()
                        gp_hr_value['cal_mul_hr']=gp_hr_value['cal_mul_hr']+ hm.get_mul_hr()
                    else:
                        hm = self.hr_managment.get('mon-thr')
                        gp_hr_value['mon-thr'] = gp_hr_value['mon-thr']+1
                        gp_hr_value['cal_hr']=gp_hr_value['cal_hr']+ hm.get_hr()
                        gp_hr_value['cal_mul_hr']=gp_hr_value['cal_mul_hr']+ hm.get_mul_hr()
                gp_hr_value['hr'] = gp_hr_value['hr'] + hm.get_hr()
                gp_hr_value['mul_hr'] = gp_hr_value['mul_hr'] + hm.get_mul_hr()
        if create_csv:
            column_headers = [key for key in checked_gp_hrs_initial_state]
            self.create_check_hrs_csv(column_headers,checked_gp_hrs)
        return checked_gp_hrs
    def create_check_hrs_csv(self,column_headers:list,data_set:dict,filename:str='checked_gp_hrs.csv'):
        with open(filename,'w',newline='') as f:
            fieldnames = ['gp']
            fieldnames.extend(column_headers)
            writer = csv.DictWriter(f,fieldnames=fieldnames)
            writer.writeheader()
            for gp,data_set_value_dict in data_set.items():
                #for each gp
                gp_value = {}
                gp_value.setdefault('gp',gp)
                for column, val in data_set_value_dict.items():
                    gp_value.setdefault(column,val)
                writer.writerow(gp_value)

        
if __name__ == "__main__":
    dt = AlertDutyScheduler(
        15,30,6,[23],["W4M","W4F","W9","MDR","IMW","ART","PSYCH"],1
    )
    def basic_wards_setup():
        # dt.set_cells_unavailable([d for d in range(dt.num_days) if not (dt.is_weekend(d) or d in dt.holiday_dates_indexes)],["W4M","W4F"],[1])
        dt.set_cells_unavailable([d for d in range(dt.num_days) if not (dt.is_weekend(d) or d in dt.holiday_dates_indexes)],["ART"])
        # dt.set_cells_unavailable([d for d in range(dt.num_days) if not (dt.is_weekend(d) or d in dt.holiday_dates_indexes)],["ART2"])
        # dt.set_cells_unavailable([d for d in range(dt.num_days) if not (dt.is_weekend(d) or d in dt.holiday_dates_indexes)],["W4M","W4F"],[1])
        # dt.set_cells_unavailable([d for d in range(dt.num_days) if dt.is_weekend(d) or d in dt.holiday_dates_indexes],["MDR"])
        dt.set_cells_unavailable([d for d in range(dt.num_days) if (d%2==0)],["PSYCH"],[])
        # dt.set_cells_unavailable([d for d in range(dt.num_days) if not(d%2==0)],["PSYCH"],[0])
        # dt.set_cells_unentry(unentry_ws=["PSYCH","ART","ART2"])
        dt.set_cells_unentry(unentry_ws=["PSYCH","ART"])
        dt.set_cells_unentry([d for d in range(dt.num_days) if not(dt.is_weekend(d) or d in dt.holiday_dates_indexes)],["MDR"])
        # dt.set_cells_unentry(unentry_ws=["W9"],unentry_ts=[1])
        # dt.set_cells_unentry(unentry_ds=[d for d in range(dt.num_days) if (dt.is_weekend(d) or d in dt.holiday_dates_indexes)], unentry_ws=["W4M","W4F"],unentry_ts=[1])
        # dt.set_cells_unentry(unentry_ds=[d for d in range(dt.num_days) if dt.is_weekend(d) or d in dt.holiday_dates_indexes],unentry_ws=["W4M","W4F"],unentry_ts=[1])
    dt.add_on_unattainable(basic_wards_setup)
    def handle_prev_duty():
        dt.add_on_prev_duty(-1,[14,8,6,3,9])
        dt.add_on_prev_duty(-2,[7,13,1,11,10])
        dt.rule_skip_prev_duty(1)
    dt.add_on_basic_rules(handle_prev_duty)
    def handle_ART_rule(if_first_day_gp_pick:list=[],ART_possible_wards:list=dt.all_wards,tt_list:list=[tt for tt in range(dt.gp_alloc_per_ward)]): #["W4M","W4F","W9"]
        for d in range(dt.num_days):
            if dt.is_weekend(d):
                if d==0: #pick gp for first day ART
                    if isinstance(if_first_day_gp_pick,list) and len(if_first_day_gp_pick):
                        dt.get_model().add(sum(dt.get_available_cell_value(gp,d,'ART',tt) for gp in if_first_day_gp_pick for tt in [0])==1) #use tt_list if you want to 
                else:
                    one_day_back = d-1
                    for gp in range(dt.num_gps):
                        prev_day_gp_duty_values = (dt.get_available_entry_cell_value(gp,one_day_back,ww,tt,0) for ww in ART_possible_wards for tt in range(dt.gp_alloc_per_ward))
                        pddgv = dt.get_model().new_bool_var(f"prev_gp{gp}_d{one_day_back}_ForART")
                        dt.get_model().add_bool_or(prev_day_gp_duty_values).only_enforce_if(pddgv)
                        dt.get_model().add(sum(dt.get_available_cell_value(gp,d,'ART',tt) for tt in [0])==0).only_enforce_if(pddgv.Not()) #can use tt_list for all values if you want
    dt.add_on_basic_rules(handle_ART_rule,[1,7],["W4M","W4F","W9"])
    # dt.add_on_unattainable(test,"y")
    # dt.run_unattainable()
    def handle_free_days_after_duty():
        # pass
        dt.rule_force_free_after_duty(2)
        # dt.rule_force_free_after_duty(1,ds=[d for d in range(9)],gps=[gp for gp in range(dt.num_gps) if not(gp in [2,4])])
        # dt.rule_force_free_after_duty(2,ds=[d for d in range(9,dt.num_days)],gps=[gp for gp in range(dt.num_gps)])
        # dt.rule_force_free_after_duty(2,ds=[d for d in range(9,dt.num_days)],gps=[gp for gp in range(dt.num_gps) if not(gp in dt.get_extra_eff_gps())])
        # dt.rule_force_free_after_duty(2,ds=[d for d in range(9,dt.num_days)],gps=[gp for gp in range(dt.num_gps) if gp in dt.get_extra_eff_gps()])
        # dt.rule_force_free_after_duty(2,ds=[d for d in range(9,dt.num_days)],gps=[gp for gp in range(dt.num_gps) if gp in dt.get_eff_gps() or gp==2])
    dt.add_on_basic_rules(handle_free_days_after_duty)
    def handle_personal_pref_added():
        # pass
        dt.skip_duty_all(2,[d for d in range(9)],True)
        dt.skip_duty_all(4,[1,2])
        dt.skip_duty(11,[1,23,28])
        dt.skip_duty(1,[1])
        dt.skip_duty(0,[1])
        dt.add_not_eff_gps([2])

        # dt.add_extra_eff_gps([gp for gp in range(dt.num_gps) if not(gp in [2,11,8,7,4,1])])
    dt.add_on_added_rules(handle_personal_pref_added)

    def handle_gp_separation():
        dt.make_two_gps_apart([ #day time same shift
            (11,12), #w4
            (1,4),#MDR
            (2,5),#ART
            (6,7),#IMW
            (0,8),#w9
        ],count_spec=True,count_spec_range=(0,0))
        dt.make_two_gps_together([(2,1)])
        # dt.make_two_gps_together([(5,11)],ws=["IMW"],count_spec=True,count_spec_range=(1,3))
    def handle_imw_diff():
        def get_imw_cell_data(gp,ds:list=[],ts:list=[],is_weekend_holiday:bool=False):
            ds = DutyScheduleTable.empty_defaulter(ds,[d for d in range(dt.num_days)])
            ts = DutyScheduleTable.empty_defaulter(ts,[t for t in range(dt.gp_alloc_per_ward)])
            if is_weekend_holiday:
                ds = [d for d in ds if dt.is_weekend(d) or d in dt.holiday_dates_indexes]
            mdr_as_imw_num_for_we_hol = (dt.get_available_entry_cell_value(gp,d,'MDR',t,0) for d in ds for t in range(dt.gp_alloc_per_ward) if dt.is_weekend(d) or d in dt.holiday_dates_indexes)
            imw_num = (dt.get_available_entry_cell_value(gp,d,'IMW',t,0) for d in ds for t in ts)
            return list(mdr_as_imw_num_for_we_hol) + list(imw_num)
        def opt_imw_diff_logic(gp,cal_gp_imw):
            dt.get_model().add(cal_gp_imw==sum(get_imw_cell_data(gp)))
        def opt_we_hol_imw_diff_logic(gp,cal_gp_imw):
            dt.get_model().add(cal_gp_imw==sum(get_imw_cell_data(gp,is_weekend_holiday=True)))
        
        max_imw_num,min_imw_num,cal_gp_imw_num = dt.max_min_opt_per_gp_helper('imw_num',dt.num_days,opt_imw_diff_logic)
        max_imw_we_hol_num,min_imw_we_hol_num,cal_gp_imw_we_hol_num = dt.max_min_opt_per_gp_helper('imw_we_hol_num',dt.num_days,opt_we_hol_imw_diff_logic)
        dt.add_on_diff_weighted_values(max_imw_num,min_imw_num,4)
        dt.add_on_diff_weighted_values(max_imw_we_hol_num,min_imw_we_hol_num,4)
        dt.add_displayable_values([max_imw_num,min_imw_num,max_imw_we_hol_num,min_imw_we_hol_num])
        dt.add_displayable_per_gp_value_dict([cal_gp_imw_num,cal_gp_imw_we_hol_num])

    def handle_personal_pref_optimization():
        
        max_set_hr = 212
        hr_diff_from_max_hr_set = dt.get_model().new_int_var(0,24*dt.num_days,f'hr_difference_from_max_hr_set')
        dt.get_model().add_abs_equality(hr_diff_from_max_hr_set,max_set_hr-dt.min_hr)
        dt.add_displayable_values([hr_diff_from_max_hr_set])
        dt.add_on_weighted_values(hr_diff_from_max_hr_set,10)
        dt.add_on_diff_weighted_values(dt.max_entry_eff_hr,dt.min_entry_eff_hr,10)
        dt.add_on_diff_weighted_values(dt.max_entry_hr,dt.min_entry_hr,5)
        # dt.get_model().add(dt.max_hr<=212)
        #gp11 stabilizer
        # dt.get_model().add(dt.cal_gp_weekend_hol_num[11]==dt.min_weekend_hol_num)
        # dt.get_model().add(dt.cal_gp_entry_eff_hr[11]==dt.min_entry_eff_hr)
        #off gps stabilizer
        # dt.get_model().add(dt.cal_gp_hr[2]<=dt.min_eff_hr-48)
        dt.get_model().add(3*dt.cal_gp_hr[2]>=2*dt.min_eff_hr)
        dt.get_model().add(6*dt.cal_gp_hr[2]<=5*dt.min_eff_hr)
        # dt.get_model().add(3*dt.cal_gp_hr[4]>=2*dt.min_eff_hr)
        # dt.get_model().add(6*dt.cal_gp_hr[4]<=5*dt.min_eff_hr)
        # dt.get_model().add(3*dt.cal_gp_entry_hr[2]>=2*dt.min_entry_eff_hr)
        # dt.get_model().add(6*dt.cal_gp_entry_hr[2]<=5*dt.min_entry_eff_hr)
        # dt.get_model().add(3*dt.cal_gp_entry_hr[4]>=2*dt.min_entry_eff_hr)
        # dt.get_model().add(6*dt.cal_gp_entry_hr[4]<=5*dt.min_entry_eff_hr)

        #eff hour stabilizer
        # dt.get_model().add(dt.min_eff_hr>=306)
        # dt.get_model().add(dt.max_eff_hr-dt.min_eff_hr<=7)
        # dt.get_model().add(dt.max_entry_eff_hr-dt.min_entry_eff_hr<=32)
        #weekend stabilizer
        # dt.get_model().add(dt.max_weekend_hol_num<=4)
        # dt.get_model().add(dt.max_weekend_hol_num-dt.min_weekend_hol_num==1)
    
    dt.add_on_optimizers(handle_gp_separation)
    dt.add_on_optimizers(handle_imw_diff)
    dt.add_on_optimizers(handle_personal_pref_optimization)
    dt.add_on_optimizers(dt.use_minimize_model)
    
    result = dt.run_all(max_min=5)
    
    if result:
        print(result)
        csv_decision = input("Do you want to create a CSV?[Y,N]").strip().lower()
        if csv_decision == 'y':
            print(dt.check_hrs_values(result,create_csv=True))
            # dt.create_csv_ward_based(result)
        else:
            sys.exit()
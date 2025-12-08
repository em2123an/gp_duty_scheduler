import csv

class DayDuty:
    def __init__(self) -> None:
        self.all_wards = ['W4M','W4F','W9','MDR','IMW','ART','PSYCH']
        self.duty_types = ['actual','signed']
        self._data = {}
    def day_data(self)-> dict:
        return self._data
    def c_w4m(self,av,sv=None):
        if av:
            self._data[(self.all_wards[0],self.duty_types[0])]=av
        if sv:
            self._data[(self.all_wards[0],self.duty_types[1])]=sv
        return self
    def c_w4f(self,av,sv=None):
        if av:
            self._data[(self.all_wards[1],self.duty_types[0])]=av
        if sv:
            self._data[(self.all_wards[1],self.duty_types[1])]=sv
        return self
    def c_w9(self,av,sv=None):
        if av:
            self._data[(self.all_wards[2],self.duty_types[0])]=av
        if sv:
            self._data[(self.all_wards[2],self.duty_types[1])]=sv
        return self
    def c_mdr(self,av,sv=None):
        if av:
            self._data[(self.all_wards[3],self.duty_types[0])]=av
        if sv:
            self._data[(self.all_wards[3],self.duty_types[1])]=sv
        return self
    def c_imw(self,av,sv=None):
        if av:
            self._data[(self.all_wards[4],self.duty_types[0])]=av
        if sv:
            self._data[(self.all_wards[4],self.duty_types[1])]=sv
        return self
    def c_art(self,av,sv=None):
        if av:
            self._data[(self.all_wards[5],self.duty_types[0])]=av
        if sv:
            self._data[(self.all_wards[5],self.duty_types[1])]=sv
        return self
    def c_psych(self,av=None,sv=None):
        if av:
            self._data[(self.all_wards[6],self.duty_types[1])]=av
        if sv:
            self._data[(self.all_wards[6],self.duty_types[1])]=sv
        return self
    def d_ward(self,w,av,sv=None):
        if(w==self.all_wards[0]):self.c_w4m(av,sv)
        elif(w==self.all_wards[1]):self.c_w4f(av,sv)
        elif(w==self.all_wards[2]):self.c_w9(av,sv)
        elif(w==self.all_wards[3]):self.c_mdr(av,sv)
        elif(w==self.all_wards[4]):self.c_imw(av,sv)
        elif(w==self.all_wards[5]):self.c_art(av,sv)
        elif(w==self.all_wards[6]):self.c_psych(av,sv)

def check_values_csv(holiday_date_index, first_day_index):
    all_wards = ['W4M','W4F','W9','MDR','IMW','ART','PSYCH']
    def get_day_of_week(d,first_day_index=first_day_index):
        # change_k = 7 - len(prev_duty_shift) if len(prev_duty_shift)<=7 else 7 - (len(prev_duty_shift)%7)
        return int(d+first_day_index)%(7) if (d+first_day_index)>=7 else int(d+first_day_index)
    
    cur_duty_data = {}
    with open('duty_csv_for_test.csv',newline='') as f:
        reader = csv.reader(f)
        date_object = {}
        for row in reader:
            d_test_object: dict = date_object.setdefault(row[0],{})
            w4m_test_object: list = d_test_object.setdefault(all_wards[0],[])
            w4m_test_object.append(row[1])
            w4f_test_object: list = d_test_object.setdefault(all_wards[1],[])
            w4f_test_object.append(row[2])
            w9_test_object: list = d_test_object.setdefault(all_wards[2],[])
            w9_test_object.append(row[3])
            mdr_test_object: list = d_test_object.setdefault(all_wards[3],[])
            mdr_test_object.append(row[4])
            imw_test_object: list = d_test_object.setdefault(all_wards[4],[])
            imw_test_object.append(row[5])
            art_test_object: list = d_test_object.setdefault(all_wards[5],[])
            art_test_object.append(row[6])
            psych_test_object: list = d_test_object.setdefault(all_wards[6],[])
            psych_test_object.append(row[7])
        for d, dv in date_object.items():
            spec_d: DayDuty = cur_duty_data.setdefault(d,DayDuty())
            for w, gpvs in dv.items():
                av = None if (not gpvs[0].strip()) else gpvs[0]
                sv = None if (not gpvs[1].strip()) else gpvs[1]
                if av or sv:
                    spec_d.d_ward(w,av,sv)
        for d, ddob in cur_duty_data.items():
            cur_duty_data[d] = ddob.day_data()
        gp_values={}
        #M-T; F; WE; ART; hrs
        for d, dv in cur_duty_data.items():
            d = int(d)
            for (w,t), gp in dv.items():
                print(d,w,t,gp)
                each_gp: dict = gp_values.setdefault(gp,{})
                gp_M_T = each_gp.setdefault('count_mon_thr',0)
                gp_F = each_gp.setdefault('count_fri',0)
                gp_WE = each_gp.setdefault('count_we',0)
                gp_ART = each_gp.setdefault('count_art',0)
                gp_hrs = each_gp.setdefault('hrs',0)
                if w==all_wards[5]:
                    #art rule
                    each_gp['count_art'] = gp_ART + 1
                    each_gp['hrs'] = gp_hrs + 8
                elif get_day_of_week(d)==5 or get_day_of_week(d)==6 or d in holiday_date_index:
                    #weekend or holiday rule
                    each_gp['count_we']=gp_WE +1
                    each_gp['hrs']=gp_hrs+24
                elif get_day_of_week(d)==4:
                    #friday rule
                    each_gp['count_fri']=gp_F+1
                    each_gp['hrs']=gp_hrs+17
                else:
                    each_gp['count_mon_thr']=gp_M_T+1
                    each_gp['hrs']=gp_hrs+16
        print(gp_values)
    with open('duty_csv_values_check.csv','w',newline='') as f:
        check_params = ['count_mon_thr','count_fri','count_we','count_art','hrs']
        fieldnames = ['gp']
        fieldnames.extend(check_params)
        writer = csv.DictWriter(f,fieldnames=fieldnames)
        for gp, gpvx in gp_values.items():
            data = {param:value for param, value in gpvx.items()}
            data['gp']=gp
            writer.writerow(data)
    

if __name__ == "__main__":
    holiday_date_index = list(map(lambda x:x-1 if x-1>=0 else 0,[29]))
    first_day_index = 2
    check_values_csv(holiday_date_index=holiday_date_index, first_day_index=first_day_index)
    
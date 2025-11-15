from tkinter import *
from tkinter import Misc, ttk, messagebox
import re
import threading
import queue
from main_version4_max_hr_only_comp import main as main_script
import time
import os
import sys
import atexit
import csv

def test_script(queue: queue.Queue, endevent: threading.Event,stopevent: threading.Event):
    for i in range(10):
        if stopevent.is_set():
            return {}
        queue.put(f'test {i}')
        print(f'test print {i}')
        time.sleep(1)
    queue.put(f'final_test')
    endevent.set()
    # time.sleep(2)
    # print('test print 2')
    print('final test print')
    return {'is_done':True}
#singleton root with data sharing 
class Root(Tk):
    _instance = None
    def __new__(cls,*args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print("first obj creation")
        return cls._instance

    def __init__(self,title="") -> None:
        print("init run")
        super().__init__()
        if not getattr(self,"_initialized",False):
            self._initialized = True
            self._data = {}
            self.set_data('number_of_gps',StringVar())
            self.set_data('required_days',StringVar())
            self.set_data('calculation_min',StringVar(value='2'))
            self.set_data('free_days_after_duty',StringVar())
            self.set_data('first_day_psych',BooleanVar())
            self.set_data('selected_model',StringVar())
            self.set_data('starting_day',IntVar())
            self.set_data('prev_duty_data',{})
            self.set_data('is_running_mainscript', BooleanVar())
            self.set_data('duty_solution', {})
            #self.root = Tk()
            self.wm_title(title) if bool(title) else None
            #self.wm_maxsize(500,480)
            self.wm_minsize(450,400)
            self.rowconfigure(0,weight=1)
            self.columnconfigure(0,weight=1)
    @staticmethod
    def get_instance(title=''):
        if Root._instance is None:
            print("first run")
            Root(title=title)
        return Root._instance        
    def run(self):
        Root.get_instance().mainloop()
    def set_data(self,key,value):
        self._data[key]=value
    def get_data(self,key,default=None):
        return self._data.get(key,default)
    def get_all_data(self):
        return dict(self._data)
    
#RootFrame
class RootFrame():
    def __init__(self,title) -> None:
        self.root = Root.get_instance(title=title)
        self.mainframe = ttk.Frame(self.root,padding="4 4 8 8")
        self.mainframe.grid(row=0, column=0, sticky=(N,S,W,E))
        self.mainframe.rowconfigure(0,weight=1)
        self.mainframe.columnconfigure(0,weight=1)
    def getmainframe(self):
        return self.mainframe
    def run(self):
        self.root.run()
#Central View Class
class CentralView(ttk.Frame):
    def __init__(self,*args, **kwargs):
        super().__init__(*args,**kwargs)
    def back_allowed(self):
        return True
    def next_allowed(self):
        return True
    def handle_cancel(self):
        return False
#Stepwise (prev,next,cancel) type of frame
class StepWiseFrame(ttk.Frame):
    def __init__(self,suproot,centerviewlist=[]):
        super().__init__(suproot)
        self.grid(row=0, column=0,sticky=(N,S,W,E))
        self.centerviewlist : list =centerviewlist
        self['borderwidth'] = 2
        self['relief'] = 'solid'
        self.viewiter=0
        #header
        self.header = ttk.Frame(self,padding="4")
        self.header.grid(row=0, column=0, sticky=(N,W,E))
        ttk.Label(self.header,text="Header Title",padding="2").grid(row=0)
        self.header['borderwidth'] = 2
        self.header['relief'] = 'solid'
        self.columnconfigure(0,weight=1)
        #main view and frame
        self.maincenterframe = ttk.Frame(self,padding="8")
        self.maincenterframe.grid(row=1, column=0,sticky=(N,S,W,E))
        self.maincenterframe['borderwidth'] = 2
        self.maincenterframe['relief'] = 'solid'
        self.columnconfigure(0,weight=2)
        self.rowconfigure(1,weight=2)
        self.cv = self._settingcenterview()
        #footer
        self.footer = ttk.Frame(self,padding="4")
        self.footer.grid(row=2, column=0, sticky=(S,E))
        self.backbtn= ttk.Button(self.footer,text="Back",padding="2",command=self.backbtncommand)
        self.backbtn.grid(row=0,column=1)
        self.nextbtn = ttk.Button(self.footer,text="Next",padding="2",command=self.nextbtncommand)
        self.nextbtn.grid(row=0,column=2)
        self.cancelbtn = ttk.Button(self.footer,text="Cancel",padding="2",command=self.cancelbtncommand)
        self.cancelbtn.grid(row=0,column=3)
        #for disabling while in progress
        r = Root.get_instance()
        running: BooleanVar = r.get_data('is_running_mainscript')
        running.trace_add('write', lambda i,v,d :self.script_running_handler(running))
        #for disabling prev and next
        self.allow_back = BooleanVar(value=True)
        self.allow_next = BooleanVar(value=True)
        self.allow_back.trace_add('write', lambda i,v,d :self.back_next_state(self.allow_back))
        self.allow_next.trace_add('write', lambda i,v,d :self.back_next_state(self.allow_next))
        self.after(0,self.check_back_next)
    
    def check_back_next(self):
        is_backable = self.cv.back_allowed()
        is_nextable = self.cv.next_allowed()
        self.allow_back.set(True) if is_backable else self.allow_back.set(False)
        self.allow_next.set(True) if is_nextable else self.allow_next.set(False)
        self.after(100,self.check_back_next)
    
    def back_next_state(self, back_or_next: BooleanVar):
        if back_or_next is self.allow_back:
            #for back
            if back_or_next.get() and self.viewiter!=0:
                self.backbtn.configure(state='normal')
            else:
                self.backbtn.configure(state='disabled')
        elif back_or_next is self.allow_next:
            #for next
            if back_or_next.get():
                self.nextbtn.configure(state='normal')
            else:
                self.nextbtn.configure(state='disabled')

    def script_running_handler(self, is_running:BooleanVar):
        if is_running.get():
            self.backbtn.configure(state='disabled')
            self.nextbtn.configure(state='disabled')
        else:
            self.backbtn.configure(state='active')
            self.nextbtn.configure(state='active')
    def backbtncommand(self):
        if self.viewiter>0:
            self.viewiter -= 1
            self._settingcenterview()
            print(self.centerviewlist)
    def nextbtncommand(self):
        if self.viewiter<len(self.centerviewlist)-1:
            self.viewiter += 1
            self._settingcenterview()
            print(self.centerviewlist)
    def cancelbtncommand(self):
        #call when cancel is called
        #look in centerview obj if it handled cancel it will return true then nothing to do
        if not self.cv.handle_cancel():
            #if false is returned, do alert box for confirmation and sys.exit or r.quit()
            if messagebox.askyesno(message="Are you sure you want to exit?", icon='question'):
                #exit
                r = Root.get_instance()
                r.quit()
                r.destroy()
    def _settingcenterview(self)->CentralView:
        if (self.centerviewlist) and len(self.centerviewlist)!=0:
            cv: ttk.Frame=self.centerviewlist[self.viewiter]
            cv.grid(row=0,column=0,sticky=(N,S,W,E))
            cv.columnconfigure(0,weight=1)
            cv.rowconfigure(0,weight=1)
            cv.tkraise()
            self.cv = cv
            print("selected:", cv)
            return cv
    def get_maincenterframe(self):
        return self.maincenterframe
    def add_centerview(self,cv):
        self.centerviewlist.append(cv)
        self._settingcenterview()
    def add_all_centerviews(self,cvs):
        self.centerviewlist.extend(cvs)
        self._settingcenterview()

#Initial configuration 
class InitStarterArgFrame(CentralView):
    def __init__(self,master):
        super().__init__(master)
        # self.columnconfigure(0,weight=1)
        # self.rowconfigure(0,weight=1)
        #self.grid(row=0, column=0,sticky=(N,W,E,S))
        r = Root.get_instance()
        #Number of GPs
        ttk.Label(self,text="Number of GPs",anchor=E).grid(row=0,column=0,pady='2')
        self.number_of_gps = r.get_data('number_of_gps')
        self.no_gps = ttk.Entry(self,textvariable=self.number_of_gps)
        self.number_of_gps.trace_add('write',lambda v,i,m: self._check_num_wrapper(self.number_of_gps))
        self.no_gps.grid(row=0,column=1,sticky=(W),pady='2')
        #Number of days for duty
        ttk.Label(self,text="How Many Days",anchor=E).grid(row=1,column=0,pady='2')
        self.required_days = r.get_data('required_days')
        self.required_days.trace_add('write',lambda v,i,m: self._check_num_wrapper(self.required_days))
        self.req_dys = ttk.Entry(self,textvariable=self.required_days)
        self.req_dys.grid(row=1,column=1,sticky=(W),pady='2')
        #Free day after duty selection
        ttk.Label(self,text="Free days after duty",anchor=E).grid(row=2,column=0,pady='2')
        self.free_days_after_duty = r.get_data('free_days_after_duty')
        self.free_days_after_duty.set('2')
        self.free_days_after_duty.trace_add('write',lambda v,i,m: self._check_num_wrapper(self.free_days_after_duty))
        self.free_dys = ttk.Entry(self,textvariable=self.free_days_after_duty)
        self.free_dys.grid(row=2,column=1,sticky=(W),pady='2')
        #Is first day psych
        ttk.Label(self,text="First day psych",anchor=E).grid(row=3,column=0,pady='2')
        self.first_day_psych = r.get_data('first_day_psych')
        fdp_tf = ttk.Frame(self)
        fdp_tf.grid(row=3,column=1,pady='2')
        ttk.Radiobutton(fdp_tf,text="True",variable=self.first_day_psych,value=True).grid(row=0,column=0,padx='2')
        ttk.Radiobutton(fdp_tf,text="False",variable=self.first_day_psych,value=False).grid(row=0,column=1,padx='2')
        #Model Selection
        ttk.Label(self,text="Model",anchor='ne').grid(row=4,column=0,pady='2')
        self.selected_model = r.get_data('selected_model')
        sm_tf = ttk.Frame(self)
        sm_tf.grid(row=4,column=1,pady='2')
        ttk.Radiobutton(sm_tf,text='Model 1',variable=self.selected_model,value='model_1').grid(row=0,column=0)
        ttk.Radiobutton(sm_tf,text='Model 2',variable=self.selected_model,value='model_2').grid(row=1,column=0)
        ttk.Radiobutton(sm_tf,text='Model 3',variable=self.selected_model,value='model_3').grid(row=2,column=0)
        ttk.Radiobutton(sm_tf,text='Model 4',variable=self.selected_model,value='model_4').grid(row=3,column=0)
        #Start Date
            #combobox with day paired with value
        ttk.Label(self,text="Starting Day",anchor='ne').grid(row=5,column=0,pady='2')
        list_of_days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        self.starting_day = r.get_data('starting_day')
        self.str_day_combo = ttk.Combobox(
            self,
            textvariable=self.starting_day,
            state='readonly',
            values=list_of_days)
        self.str_day_combo.grid(row=5,column=1,pady='2')
        self.str_day_combo.current(self.starting_day.get())
        self.str_day_combo.bind('<<ComboboxSelected>>',lambda x:self._on_select_str_day_combo())
        #Calculation Minutes (maximum)
        ttk.Label(self,text="Calculation Max. Minutes",anchor=E).grid(row=6,column=0,pady='2')
        self.calculation_min = r.get_data('calculation_min')
        self.calculation_min.trace_add('write',lambda v,i,m: self._check_num_wrapper(self.calculation_min))
        self.cal_min = ttk.Entry(self,textvariable=self.calculation_min)
        self.cal_min.grid(row=6,column=1,sticky=(W),pady='2')

    def _check_num_wrapper(self,var:StringVar):
        value = var.get()
        if value=='': return
        if not value.isdigit():
            var.set(''.join(filter(str.isdigit,value)))
        # value = self.number_of_gps.get()
        # if value=='': return
        # if not value.isdigit():
        #     self.number_of_gps.set(''.join(filter(str.isdigit,value)))
    def _on_select_str_day_combo(self):
        newidx = self.str_day_combo.current()
        self.starting_day.set(newidx)
    def next_allowed(self):
        #return True #testing
        r = Root.get_instance()
        """
        self.set_data('number_of_gps',StringVar())
            self.set_data('required_days',StringVar())
            self.set_data('calculation_min',StringVar(value='2'))
            self.set_data('free_days_after_duty',StringVar())
            self.set_data('first_day_psych',BooleanVar())
            self.set_data('selected_model',StringVar())
            self.set_data('starting_day',IntVar())
            self.set_data('prev_duty_data',{})
        """
        v_values = (bool(r.get_data('number_of_gps').get()), 
                    bool(r.get_data('required_days').get()),
                    bool(r.get_data('calculation_min').get()),
                    bool(r.get_data('free_days_after_duty').get())
        )
        return all(v_values)
#Previous Duty setting
class PrevDutyScedFrame(CentralView):
    wardlist = ["W4M","W4F","W9","IMW1","IMW2"]
    lastdaystocount = 3
    def __init__(self, master):
        super().__init__(master)
        r = Root.get_instance()
        startheadercolumn = 1
        startvaluerow = 2
        # numgps = int(r.get_data('number_of_gps').get()) if r.get_data('number_of_gps').get().isdigit() else 0
        ttk.Label(self,text="Previous Duty Schedule Last days",anchor=E).grid(row=0,rowspan=3)
        r.set_data('prev_duty_data',{(w,d):StringVar() for w in PrevDutyScedFrame.wardlist for d in range(PrevDutyScedFrame.lastdaystocount)})
        prevdutystates = r.get_data('prev_duty_data')
        self.combostates = {}
        for i,ww in enumerate(PrevDutyScedFrame.wardlist):
            ttk.Label(self,text=ww,anchor=E).grid(row=1,column=startheadercolumn+i)
        for dd in range(PrevDutyScedFrame.lastdaystocount):
            ttk.Label(self,text=f'{dd+1}:',anchor=E).grid(row=startvaluerow+dd,column=0)
            for i,ww in enumerate(PrevDutyScedFrame.wardlist):
                self.combostates[(ww,dd)] = ttk.Combobox(
                    self,
                    textvariable=prevdutystates[(ww,dd)],
                    width=3,
                    state='readonly'
                    )
                self.combostates[(ww,dd)].grid(row=startvaluerow+dd,column=startheadercolumn+i,sticky=W)
        nogpstate: StringVar = r.get_data('number_of_gps')
        nogpstate.trace_add('write',lambda v,i,m:self.update_values_gps(nogpstate))
        # ttk.Label(self,text="W4F",anchor='center').grid(row=1,column=2)
        # ttk.Label(self,text="W9",anchor='center').grid(row=1,column=3)
        # ttk.Label(self,text="IMW1",anchor='center').grid(row=1,column=4)
        # ttk.Label(self,text="IMW2",anchor='center').grid(row=1,column=5)
        # ttk.Label(self,text="03:",anchor=E).grid(row=2,column=0)
        # ttk.Label(self,text="02:",anchor=E).grid(row=3,column=0)
        # ttk.Label(self,text="01 (last day):",anchor=E).grid(row=4,column=0)
    def update_values_gps(self,nogpstate: StringVar):
        num_gps = int(nogpstate.get()) if nogpstate.get().isdigit() else 0
        for dd in range(PrevDutyScedFrame.lastdaystocount):
            for ww in PrevDutyScedFrame.wardlist:
                self.combostates[(ww,dd)]['values']=[gpi for gpi in range(num_gps)]
    def next_allowed(self):
        # return True #testing
        r = Root.get_instance()
        prevdutystates = r.get_data('prev_duty_data')
        if prevdutystates and all([
            bool(str(prevdutystates[(ww,dd)].get())) 
            for ww in PrevDutyScedFrame.wardlist 
            for dd in range(PrevDutyScedFrame.lastdaystocount)
            ]):
            
            return True 
        else:
            return False
#Main Script Running Frame
class MainLogicScriptRun(CentralView):
    def __init__(self,master):
        super().__init__(master)
        r = Root.get_instance()
        self.workers :list[self._Worker] = []
        self.startbtn = ttk.Button(self,text="Start",command=self.mainscriptstarter)
        self.startbtn.grid(row=0,column=0)
        self.msg_queue = queue.Queue()
        self.output_box = OutputBox(self,row=2,queue=self.msg_queue)
        self.progressbar = ttk.Progressbar(self,orient="horizontal", length=240, mode='determinate')
        self.progressbar.grid(row=1,column=0)
        self.progressbar.grid_remove()
        self.prgbarvariable = IntVar(value=0)
        self.progressbar.configure(variable=self.prgbarvariable)
        self.maxmin = self.get_int_key('calculation_min')
        self.max_sec = self.maxmin * 60
        self.temp_duty_solution = {}
        self.is_data_exportable = BooleanVar()
        self.export_btn = ttk.Button(self,text="Export",command=self.export_command)
        self.export_btn.grid(row=3)
        self.export_btn.configure(state='disabled')

        running: BooleanVar = r.get_data('is_running_mainscript')
        running.trace_add('write', lambda i,v,d :self.script_running_handler(running))
        self.is_data_exportable.trace_add('write', lambda i,v,d: self.exportable_data_handler(self.is_data_exportable))

        maxcalmin: StringVar = r.get_data('calculation_min')
        maxcalmin.trace_add('write', lambda i,v,d :self.progressbar_maximum())
        
        # self.output_text = Text(self,width=40, height=10, wrap='word')
        # ys = ttk.Scrollbar(self,orient='vertical',command=self.output_text.yview)
        # self.output_text['yscrollcommand']=ys.set
        # self.output_text.grid(row=1,column=0,columnspan=3)
        # ys.grid(row=1,column=4,sticky=(N,S))
    def progressbar_maximum(self):
        self.maxmin = self.get_int_key('calculation_min')
        self.max_sec = self.maxmin * 60
        self.progressbar.configure(maximum=self.max_sec)

    def export_command(self):
        r = Root.get_instance()
        ds = r.get_data('duty_solution')
        bcgthread = threading.Thread(target=self._export_by_csv,args=(ds,),name='export_csv',daemon=True)
        bcgthread.start()
    def exportable_data_handler(self, is_exportable:BooleanVar):
        if is_exportable.get():
            self.export_btn.configure(state='active')
        else:
            self.export_btn.configure(state='disabled')
    def inc_progress(self, is_running):
        if is_running.get() and self.prgbarvariable.get() < self.max_sec:
            self.prgbarvariable.set(self.prgbarvariable.get()+1)
            self.progressbar.after(1000,self.inc_progress, is_running)
    def reset_progress(self):
        self.prgbarvariable.set(0)
    def script_running_handler(self, is_running:BooleanVar):
        if is_running.get():
            self.startbtn.configure(state='disabled')
            self.progressbar.grid()
            self.progressbar.after(0,self.inc_progress, is_running)
            self.is_data_exportable.set(False)
        else:
            self.startbtn.configure(state='active')
            self.progressbar.after(100,self.reset_progress)
            self.progressbar.grid_remove()
            r = Root.get_instance()
    
    def handle_cancel(self):
        r = Root.get_instance()
        is_running: BooleanVar = r.get_data('is_running_mainscript')
        if is_running.get():
            for w in self.workers:
                w.stop()
            return True
        else:
            return False
    
    def mainscriptstarter(self):
        r = Root.get_instance()
        r.get_data('is_running_mainscript').set(True)
        # endevent = threading.Event()
        # bcgthread = threading.Thread(target=self.miniscript,args=(endevent,),name='main_bg_logic',daemon=True)
        # bcgthread.start()
        new_worker = self._Worker(self.mainscript)
        new_worker.start()
        self.workers.append(new_worker)
        self.check_script_running(new_worker,r,new_worker.end_event)
        
    def check_script_running(self, bcgt: threading.Thread, r: Root,endevent: threading.Event):
        if endevent.is_set():
            r.set_data('duty_solution',self.temp_duty_solution)
            self.is_data_exportable.set(True)
        if bcgt.is_alive():
            r.after(100,self.check_script_running,bcgt,r,endevent)
        else:
            r.get_data('is_running_mainscript').set(False)
            endevent.clear()
    def miniscript(self, end_event: threading.Event, stop_event=threading.Event()):
        self.temp_duty_solution = test_script(self.msg_queue,end_event, stop_event)
    def mainscript(self, end_event=threading.Event(), stop_event=threading.Event()):
        r = Root.get_instance()
        numgps = self.get_int_key('number_of_gps')
        numdys = self.get_int_key('required_days')         
        maxmin = self.get_int_key('calculation_min')         
        freedysad = self.get_int_key('free_days_after_duty')
        firstpscd = r.get_data('first_day_psych').get()
        firstdidx = r.get_data('starting_day').get()
        self.temp_duty_solution=main_script(
            d_num_gps=numgps,
            d_num_days=numdys,
            d_freedays_after_duty=freedysad,
            d_is_first_day_psych=firstpscd,
            d_first_day_index=firstdidx,
            d_max_min=maxmin,
            d_prev_duty_shift=self.map_prev_duty_for_mainscript(),
            msg_queue=self.msg_queue,
            end_event=end_event,
            stop_event=stop_event
        )
    def get_int_key(self,key):
        r = Root.get_instance()
        return int(r.get_data(key).get()) if r.get_data(key).get().isdigit() else 0
    def map_prev_duty_for_mainscript(self):
        #duty_types = ['actual','signed']
        prevdutywardnaming = PrevDutyScedFrame.wardlist #["W4M","W4F","W9","IMW1","IMW2"]
        lastdaystocount = PrevDutyScedFrame.lastdaystocount #3
        r = Root.get_instance()
        prevdutydata = r.get_data('prev_duty_data')
        newmapdict = {}
        for (ww,dd), gp in prevdutydata.items():
            if ww=="IMW1" or ww=="IMW2":
                newmapdict.setdefault(dd,{}).setdefault("IMW",[]).append(int(gp.get()) if gp.get().isdigit() else None)
            else:
                newmapdict.setdefault(dd,{})[ww] = int(gp.get()) if gp.get().isdigit() else None
        return newmapdict
    def _export_by_csv(self,duty_solution):
        all_wards = ['W4M','W4F','W9','MDR','IMW','ART','PSYCH']
        duty_types = ['actual','signed']
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
    def back_allowed(self):
        return True
    def next_allowed(self):
        return False
    class _Worker(threading.Thread):
        def __init__(self, _mainscript, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.stop_event = threading.Event()
            self.end_event = threading.Event()
            self._mainscript = _mainscript
        def stop(self):
            self.stop_event.set()
        def run(self):
            self._mainscript(end_event=self.end_event, stop_event=self.stop_event)

#Output Displaying Textbox
class OutputBox(Text):
    def __init__(self,master,row,queue: queue.Queue):
        super().__init__(master,width=40, height=10, wrap='word')
        ys = ttk.Scrollbar(master,orient='vertical',command=self.yview)
        self['yscrollcommand']=ys.set
        self.grid(row=row,column=0,columnspan=3)
        ys.grid(row=row,column=4,sticky=(N,S))
        self.msg_queue = queue
        self.after(100,self.update_text)
    
    def update_text(self):
        while not self.msg_queue.empty():
            msg = self.msg_queue.get_nowait()
            self.configure(state='normal')
            self.insert(END,msg)
            self.configure(state='disabled')
            self.see(END)
        self.after(100,self.update_text)

if __name__ == "__main__":
    root = RootFrame(title="GP Scheduler")
    mainframe = root.getmainframe()
    sw = StepWiseFrame(mainframe)
    mcf = sw.get_maincenterframe()
    cv1 = InitStarterArgFrame(mcf)
    cv2 = PrevDutyScedFrame(mcf)
    cv3 = MainLogicScriptRun(mcf)
    # cv3 = ttk.Label(mcf,text="Center 3")
    sw.add_all_centerviews([cv1,cv2,cv3])
    root.run()
"""Full-screen touch UI; withdrawing the window leaves the Pi agent running."""
import argparse
import io
import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageTk, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display
from service import Service

def display(text):
    return get_display(arabic_reshaper.reshape(text)) if any('\u0600'<=c<='\u06ff' for c in text) else text

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',default=str(Path(__file__).with_name('config.json'))); parser.add_argument('--windowed',action='store_true'); parser.add_argument('--offline',action='store_true'); args=parser.parse_args()
    os.environ['TZ']='Asia/Kuwait'
    if hasattr(time,'tzset'): time.tzset()
    config=json.loads(Path(args.config).read_text()) if Path(args.config).exists() else {'camera':'auto'}
    env_file=Path(__file__).with_name('.env')
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key,separator,value=line.partition('=')
            if separator and key.strip()=='OPENAI_API_KEY':os.environ.setdefault('OPENAI_API_KEY',value.strip().strip('\"\''))
    if args.offline: config['apiBase']=''
    service=Service(config)
    root=tk.Tk(); root.title('Noor · Your everyday companion'); root.geometry('800x480'); root.attributes('-fullscreen',not args.windowed); root.minsize(640,400)
    zoom=tk.DoubleVar(value=1); language=tk.StringVar(); voice=tk.StringVar(); face=tk.BooleanVar(); scene=tk.BooleanVar(); speech=tk.BooleanVar(); status=tk.StringVar(); clock=tk.StringVar(); frame_ref=[None]; last_frame=[None]; last_theme=[None]; last_desc=[None]; visible=[True]; language_seen=[None]
    colors={}; text_widgets=[]; busy=[False]
    def label(parent,key,en,ar,**kw):
        widget=tk.Label(parent,**kw); text_widgets.append((widget,key,en,ar)); return widget
    outer=tk.Frame(root); outer.pack(fill='both',expand=True)
    header=tk.Frame(outer,height=55); header.pack(fill='x',padx=18,pady=(12,5))
    brand=tk.Label(header,text='✦ noor',font=('Arial',25,'bold')); brand.pack(side='left')
    tk.Label(header,textvariable=clock,font=('Arial',12)).pack(side='right',padx=12)
    def toggle_full():
        full=not bool(root.attributes('-fullscreen'))
        root.attributes('-fullscreen',full)
        screen_button.configure(text='▣' if full else '⛶')
    screen_button=tk.Button(header,text='▣' if not args.windowed else '⛶',font=('Arial',19),bd=0,command=toggle_full)
    screen_button.pack(side='right',padx=(4,8))
    lens=tk.Button(header,text='⌕',font=('Arial',19),bd=0,command=lambda:zoom_bar.pack_forget() if zoom_bar.winfo_manager() else zoom_bar.pack(after=header,fill='x',padx=18)); lens.pack(side='right')
    zoom_bar=tk.Frame(outer)
    zoom_percent=tk.StringVar(value='100%')
    tk.Label(zoom_bar,textvariable=zoom_percent,font=('Arial',11)).pack(side='right',padx=8)
    ttk.Scale(zoom_bar,from_=.6,to=2.0,variable=zoom,command=lambda _:scale()).pack(side='left',fill='x',expand=True)
    layout=tk.Frame(outer); layout.pack(fill='both',expand=True,padx=18,pady=(5,10)); layout.columnconfigure(0,weight=3);layout.columnconfigure(1,weight=1,minsize=210);layout.rowconfigure(0,weight=1)
    left=tk.Frame(layout);left.grid(row=0,column=0,sticky='nsew',padx=(0,14)); camera=tk.Canvas(left,bg='#202439',highlightthickness=0); camera.pack(fill='both',expand=True)
    description=tk.Text(left,height=4,wrap='word',relief='flat',padx=12,pady=10,font=('Arial',16)); description.pack(fill='x',pady=(10,0)); description.configure(state='disabled')
    right=tk.Frame(layout,padx=14,pady=14);right.grid(row=0,column=1,sticky='nsew')
    label(right,'ready','Your everyday companion','رفيقك كل يوم',font=('Arial',12,'bold'),wraplength=195).pack(anchor='w',pady=(0,12))
    def analyse(): service.enqueue('local-'+str(time.time()),{'type':'analyse'},'local')
    analyse_button=tk.Button(right,command=analyse,relief='flat',bd=0,pady=14,font=('Arial',16,'bold'));analyse_button.pack(fill='x',pady=(0,15));text_widgets.append((analyse_button,'analyse','✦ Describe the scene','✦ وصف المشهد'))
    def save(key,value):
        service.update_setting(key,value)
        def worker():
            try:
                if service.cloud: service.cloud.api('settings',{key:value})
            except Exception as exc: service.message=str(exc)
        threading.Thread(target=worker,daemon=True).start()
    face_button=tk.Checkbutton(right,variable=face,command=lambda:save('faceRecognition',face.get()),font=('Arial',12),anchor='w',wraplength=185);face_button.pack(fill='x',pady=7);text_widgets.append((face_button,'face','Familiar faces','التعرف على الوجوه'))
    scene_button=tk.Checkbutton(right,variable=scene,command=lambda:save('sceneDescription',scene.get()),font=('Arial',12),anchor='w');scene_button.pack(fill='x',pady=7);text_widgets.append((scene_button,'scene','Describe scenes','وصف المشهد'))
    speech_button=tk.Checkbutton(right,variable=speech,command=lambda:save('speech',speech.get()),font=('Arial',12),anchor='w');speech_button.pack(fill='x',pady=7);text_widgets.append((speech_button,'speech','Read aloud','قراءة بصوت عالٍ'))
    language_box=ttk.Combobox(right,textvariable=language,values=['ar','en'],state='readonly',width=15,font=('Arial',12));language_box.pack(fill='x',pady=8);language_box.bind('<<ComboboxSelected>>',lambda _:save('language',language.get()))
    voice_box=ttk.Combobox(right,textvariable=voice,values=__import__('core').VOICES,state='readonly',width=15,font=('Arial',12));voice_box.pack(fill='x',pady=8);voice_box.bind('<<ComboboxSelected>>',lambda _:save('voice',voice.get()))
    theme_button=tk.Button(right,command=lambda:save('theme','light' if service.settings().get('theme')=='dark' else 'dark'),relief='flat',pady=9);theme_button.pack(fill='x',pady=8);text_widgets.append((theme_button,'theme','◐ Change appearance','◐ تغيير المظهر'))
    bottom=tk.Frame(outer); bottom.pack(fill='x',padx=18,pady=(0,10));tk.Label(bottom,textvariable=status,font=('Arial',10),anchor='w',wraplength=650).pack(side='left',fill='x',expand=True)
    def scale():
        zoom_percent.set(f'{round(zoom.get()*100)}%')
        frame_ref[0]=None  # Re-render the current live frame at the new zoom.
        description.configure(font=('Arial',int(16*zoom.get())))
        analyse_button.configure(font=('Arial',int(16*zoom.get()),'bold'))
        for w,key,en,ar in text_widgets:
            if w!=analyse_button:w.configure(font=('Arial',int(12*zoom.get())))
    def paint(theme):
        dark=theme=='dark'; bg='#171826' if dark else '#f4f3fb'; card='#27283b' if dark else '#ffffff'; fg='#f2efff' if dark else '#302b46'; accent='#8b75f5' if dark else '#6956df'
        root.configure(bg=bg)
        def recurse(w):
            if isinstance(w,(tk.Frame,tk.Label,tk.Checkbutton,tk.Button)) and w!=camera:
                w.configure(bg=card if w==right or w.master==right else bg)
                if isinstance(w,(tk.Label,tk.Checkbutton,tk.Button)):w.configure(fg=fg)
                if isinstance(w,tk.Checkbutton):w.configure(selectcolor=card,activebackground=card,activeforeground=fg)
            for child in w.winfo_children():recurse(child)
        recurse(outer);brand.configure(fg=accent);analyse_button.configure(bg=accent,fg='white',activebackground=accent,activeforeground='white');description.configure(bg=card,fg=fg,insertbackground=fg)
    def hide():
        save('uiVisible',False);root.withdraw();visible[0]=False;service.ui_visible=False
    root.protocol('WM_DELETE_WINDOW',hide)
    root.bind('<Escape>',lambda _:root.attributes('-fullscreen',False) or screen_button.configure(text='⛶'))
    def render_camera(raw):
        width,height=max(20,camera.winfo_width()),max(20,camera.winfo_height())
        if not raw:
            camera.delete('all')
            camera.create_text(width//2,height//2,text='Connecting to your camera…',fill='#d9d4f0',font=('Arial',16))
            return
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            fit=min(width/image.width,height/image.height)
            size=(max(1,round(image.width*fit*zoom.get())),max(1,round(image.height*fit*zoom.get())))
            image=image.resize(size,Image.Resampling.BILINEAR)
            photo=ImageTk.PhotoImage(image)
        camera.delete('all')
        camera.create_image(width//2,height//2,image=photo,anchor='center')
        camera.image=photo  # Keep the current frame alive while Tk displays it.
    def poll():
        settings=service.settings(); lang=settings.get('language','ar'); theme=settings.get('theme','light')
        desired=settings.get('uiVisible',True)
        if desired!=visible[0]:
            root.deiconify() if desired else root.withdraw(); visible[0]=desired
        service.ui_visible=visible[0]
        if theme!=last_theme[0]:paint(theme);last_theme[0]=theme
        if lang!=language_seen[0]:
            for w,key,en,ar in text_widgets:w.configure(text=display(ar if lang=='ar' else en))
            language_seen[0]=lang;last_desc[0]=None
        if not language_box.instate(['focus']):language.set(lang)
        if not voice_box.instate(['focus']):voice.set(settings.get('voice','marin'))
        face.set(settings.get('faceRecognition',False));scene.set(settings.get('sceneDescription',True));speech.set(settings.get('speech',True));analyse_button.configure(state='disabled' if service.busy or not scene.get() else 'normal')
        clock.set(datetime.now(ZoneInfo('Asia/Kuwait')).strftime('%I:%M %p'))
        status.set(display(('● Camera online' if service.camera_ok else '○ Camera reconnecting')+'  ·  '+('Cloud connected' if service.cloud_ok else 'Cloud offline')+'  ·  '+service.message[:100]))
        if service.description!=last_desc[0]:
            description.configure(state='normal');description.delete('1.0','end');description.insert('end',display(service.description));description.tag_configure('align',justify='right' if lang=='ar' else 'left');description.tag_add('align','1.0','end');description.configure(state='disabled');last_desc[0]=service.description
        raw=service.frame
        size=(camera.winfo_width(),camera.winfo_height(),round(zoom.get(),2))
        if raw is not last_frame[0] or size!=frame_ref[0]:
            try:
                render_camera(raw);last_frame[0]=raw;frame_ref[0]=size
            except Exception:pass
        root.after(120,poll)
    service.start();poll()
    try:root.mainloop()
    finally:service.stop.set()

if __name__=='__main__':main()

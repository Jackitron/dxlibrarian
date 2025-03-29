# Simple Tkinter User interface for Yamaha Reface DX patch librarian
# Capable of sending sysex patches in the directory to the synth, or downloading data from the synth as new sysex files.
# Jack Edwards
import os
import sys
import mido
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from datetime import datetime

######## Globals

# Number of times refresh button clicked
timesRefreshed = 0

# Unique reface DX identity request
DX_ID = mido.Message.from_bytes([0xf0, 0x7e, 0x01, 0x06, 0x01, 0xf7])
# And expected response
DX_ID_VALID = [0xf0, 0x7e, 0x7f, 0x06, 0x02, 0x43, 0x00, 0x41, 0x53, 0x06, 0x03, 0x00, 0x00, 0x7f, 0xf7]

# Parameter database in format (HIGH,MID,LOW)
# Programatically generated from original yamaha spec https://usa.yamaha.com/files/download/other_assets/7/794817/reface_en_dl_b0.pdf
# Much better than typing everything out!

# Start with 10 bytes for voice name
DXP_NAME = [ (0x30, 0x00, x) for x in range(0x00, 0x0a)]
DXP_PARAMS = [ (0x30, 0x00, x) for x in range(0x0c, 0x23)]
DXP_OP1 = [ (0x31, 0x00, x) for x in range(0x00, 0x19)]
DXP_OP2 = [ (0x31, 0x01, x) for x in range(0x00, 0x19)]
DXP_OP3 = [ (0x31, 0x02, x) for x in range(0x00, 0x19)]
DXP_OP4 = [ (0x31, 0x03, x) for x in range(0x00, 0x19)]
# Then 20 bytes from 0x0d for voice parameters
PARAMETERS = DXP_NAME + DXP_PARAMS + DXP_OP1 + DXP_OP2 + DXP_OP3 + DXP_OP4
SYX_SIZE = len(PARAMETERS)


def SetMidiDevice(s):
    print('Setting midi port to',s)

# Refresh the current directory and patch files
# For speed, only list current pwd and one level down
def RefreshFiles():
    # Clear all entries in the treeview - does this clear child items as well?
    for c in patchFiles.get_children():
        patchFiles.delete(c)
    dirs=[]
    tagIndex = 0;
    # Add directories/top level things first
    for fd in os.listdir():
        if os.path.isdir(fd):
            dirs.append(fd+'/')
            patchFiles.insert('',1,iid=fd+'/', text=fd, values=('Folder'), tag='folder')
        # If not directories, are they sysex files?
        elif '.syx' in fd:
            patchFiles.insert('',1,iid=fd, text=fd, values=(GetTimeLastModified(os.path.abspath(fd))), tag='patch')

    # And do files one level down
    for d in dirs:
        for f in os.listdir(d):
            # Hide entries that are not sysex patches
            if '.syx' in f:
                patchFiles.insert(d,1,iid=d+f, text=f, values=(GetTimeLastModified(os.path.abspath(fd))), tag='patch')

# Get the date + time a file was modified
def GetTimeLastModified(p):
    mtime = os.path.getmtime(p)
    dd = datetime.fromtimestamp(mtime)
    return dd.strftime('%H:%M\ \ \ %d/%m/%y')



# Update the list of MIDI ports available to the program
def RefreshMidi():
    # Acknowledge
    global connectedDevice
    global timesRefreshed
    timesRefreshed += 1
    refreshBtn['text'] = "(" + str(timesRefreshed) + ") Refresh"

    # If a device was selected, back up textvar for after
    # (prevents reopening and closing?)
    lastDev = ''
    if len(connectedDevice.get()) > 1:
        lastDev = connectedDevice.get()
    
    print(str(timesRefreshed) + ': Refreshing Midi Devices...')
    found = []

    for p in mido.get_output_names():
        print("Discovered '"+str(p)+"'")
        found.append(p)

    # Default
    midiBox.set_menu('', *found)
    # OR, restore backup from selected?
    if len(lastDev) > 1:
        if lastDev in found:
            midiBox.set_menu(lastDev, *found)
    
    # And refresh file list
    RefreshFiles()




# Upload selected file to DX
def UploadSelected():
    global connectedDevice
    # Turn treeview's selection into path
    fpath = os.getcwd() +'/'+ patchFiles.focus()
    print(fpath)

    voiceBytes = [0 for i in range(SYX_SIZE)]
    try:
        with open(fpath,'rb') as fd:
            voiceBytes = fd.read()
        print("Found file '"+fpath+"'")
    except Exception as err:
        messagebox.showwarning('Cannot Upload!', str(err))

    with mido.open_input(connectedDevice.get()) as response:
        with mido.open_output(connectedDevice.get()) as request:
            # First send ID request
            request.send(DX_ID)
            # Wait for identity reply
            msg = response.receive()
            while msg.bytes()[0] != 0xf0:
                msg = response.receive()

            if msg.bytes() == DX_ID_VALID:
                print("Device ID Valid! (0x53, Reface DX)")
                print("Sending patch...")
                idx = 0
                for p in PARAMETERS:
                    request.send(mido.Message('sysex', data=[ 0x43, 0x10, 0x7f, 0x1c, 0x05, p[0], p[1], p[2], voiceBytes[idx] ] ))
                    # Wait for any reply to sync sending?
                    msg = response.receive()
                    #print()
                    idx += 1
                # Done
                print("\n Upload completed: '"+fpath+"'")
                messagebox.showinfo('Reface DX', 'Upload Complete.')
            else:
                print("Midi Device not recognised.")
                messagebox.showwarning('Device not Recognised', 'The chosen MIDI device is not a Reface DX!')



# Download current DX patch to file (Save As)
def RequestPatch():
    global connectedDevice
    print("Opening port to",connectedDevice.get())
    voiceBytes = [0 for i in range(SYX_SIZE)]

    if len(connectedDevice.get()) < 1:
        messagebox.showwarning('Device not Recognised', 'That is not a MIDI device.')
        return

    with mido.open_input(connectedDevice.get()) as response:
        with mido.open_output(connectedDevice.get()) as request:
            # First send ID request
            request.send(DX_ID)
            # Wait for identity reply
            msg = response.receive()
            while msg.bytes()[0] != 0xf0:
                msg = response.receive()

            if msg.bytes() == DX_ID_VALID:
                print("Device ID Valid! (0x53, Reface DX)")

                # Begin parameter dump!
                idx = 0
                for p in PARAMETERS:
                    request.send(mido.Message('sysex', data=[0x43,0x30,0x7f,0x1c,0x05, p[0],p[1],p[2]] ))
                    # Pull responses out
                    gotByte = False
                    for msg in response:
                        if msg.type == 'sysex':
                            # Parameter is usually second to last
                            voiceBytes[idx] = msg.bytes()[-2]
                            idx += 1
                            gotByte = True
                            break
                    # Warn user if unthinkable happens?
                    if gotByte == False:
                        print("General error - Reface did not return sysex parameter on request.")
                        messagebox.showwarning('Caution', 'General I/O Error. Reface did not return parameter upon request.\nPatch may not be copied properly!')
            else:
                print("Midi Device not recognised.")
                messagebox.showwarning('Device not Recognised', 'The chosen MIDI device is not a Reface DX!')
                return

    # Make default name from patch?
    patchName = ""
    for c in voiceBytes[:10]:
        patchName += chr(c)
    patchName = patchName.strip().replace('/','').replace('\\','£') + ".syx"

    # Open file dialog
    fpath = filedialog.asksaveasfilename(initialdir = os.getcwd(),initialfile=patchName,title = "Save System-Exclusive Patch As...", defaultextension='.syx', filetypes = [("sysex files","*.syx")] )
    # Save file, or cancel
    if len(fpath) > 1:
        with open(fpath,'wb') as fd:
            fd.write( bytearray(voiceBytes) )
        print("Wrote file '"+fpath+"'")
    else:
        messagebox.showwarning('User Cancel', 'File not written.')

    # Refresh file list
    RefreshFiles()



# Or rename current patch using a nearby string:
def GetPatchName():
    global connectedDevice
    print("Opening port to",connectedDevice.get())
    nameBytes = [0 for i in range(len(DXP_NAME))]

    if len(connectedDevice.get()) < 1:
        messagebox.showwarning('Device not Recognised', 'That is not a MIDI device.')
        easyPatchName.set('Dyna Choir')
        return

    with mido.open_input(connectedDevice.get()) as response:
        with mido.open_output(connectedDevice.get()) as request:
            # First send ID request
            request.send(DX_ID)
            # Wait for identity reply
            msg = response.receive()
            while msg.bytes()[0] != 0xf0:
                msg = response.receive()

            if msg.bytes() == DX_ID_VALID:
                print("Device ID Valid! (0x53, Reface DX)")
                print("Getting name...")
                idx = 0
                for p in DXP_NAME:
                    request.send(mido.Message('sysex', data=[0x43,0x30,0x7f,0x1c,0x05, p[0],p[1],p[2]] ))
                    # Wait for any reply to sync sending?
                    for msg in response:
                        if msg.type == 'sysex':
                            # Parameter is usually second to last
                            nameBytes[idx] = msg.bytes()[-2]
                            break
                    idx += 1
            else:
                print("Midi Device not recognised.")
                messagebox.showwarning('Device not Recognised', 'The chosen MIDI device is not a Reface DX!')

    # Finally put name in librarian
    nameStr = ""
    for n in nameBytes:
        nameStr += chr(n)
    easyPatchName.set( nameStr.replace('/','').replace('\\','£') )
    print("Got name from DX:", easyPatchName.get() )



def SetPatchName():
    global connectedDevice
    print("Opening port to",connectedDevice.get())
    nameBytes = []

    # Add emergency spaces in case user is a dunce (100% guaranteed)
    # No exceptions here baby. Sometimes, my genius...
    nameStr = easyPatchName.get() + "          "
    for c in nameStr[0:10]:
        nameBytes.append(ord(c))
        print(c)

    if len(connectedDevice.get()) < 1:
        messagebox.showwarning('Device not Recognised', 'That is not a MIDI device.')
        return

    with mido.open_input(connectedDevice.get()) as response:
        with mido.open_output(connectedDevice.get()) as request:
            # First send ID request
            request.send(DX_ID)
            # Wait for identity reply
            msg = response.receive()
            while msg.bytes()[0] != 0xf0:
                msg = response.receive()

            if msg.bytes() == DX_ID_VALID:
                print("Device ID Valid! (0x53, Reface DX)")
                print("Setting name bytes:")
                idx = 0
                for p in DXP_NAME:
                    request.send(mido.Message('sysex', data=[ 0x43, 0x10, 0x7f, 0x1c, 0x05, p[0], p[1], p[2], nameBytes[idx] ] ))
                    # Wait for any reply to sync sending?
                    msg = response.receive()
                    idx += 1
            else:
                print("Midi Device not recognised.")
                messagebox.showwarning('Device not Recognised', 'The chosen MIDI device is not a Reface DX!') 
    print("Sent name", nameStr)


# Creates a window with a midi selector, tree view of files, upload, save as and rename
root = Tk()
root.title('Yamaha Reface DX Librarian')
root.geometry('480x640')
root.grid_columnconfigure(0, weight=1)

##### Tkinter specific variables
# Actual name of MIDI device for mido
connectedDevice = StringVar()

# Apply Basic theme
style = ttk.Style()
style.theme_use('clam')

style.configure('.', relief='flat', foreground="White", background='#303451', font=('Ubuntu', 11))

style.map('TMenubutton',
    background=[ ('pressed', '#44a'), ('','#557') ],
    fieldbackground=[('','#445'),('active', '#0f0')],
    padding=[ ('', '4') ],
)

style.configure("TMenubutton.Menu", background='#557',fieldbackground='#113')

style.configure("TEntry",fieldbackground='#557',padding='5')

style.map('TButton',
    background=[ ('pressed', '#44a'), ('active', '#668'), ('!pressed', '#557') ],
    padding=[ ('pressed','6'), ('!pressed','4') ],
)
style.configure("Treeview", background='#557',fieldbackground='#113')

#print(style.layout('TMenubutton'))
#print(style.element_options('Treeview.highlight'))

midiPanel = ttk.Frame(root)
midiPanel.pack(fill='both', expand='false')
################################################################################ MIDI Selector and refresh button.
ttk.Label(midiPanel, text='Select MIDI Device: ').pack(side='top', fill='x', expand='false')
midiBox = ttk.OptionMenu(midiPanel, connectedDevice ,command=SetMidiDevice)
midiBox.pack(side='right', fill='x', expand='true')
aaa = Menu(midiPanel)
refreshBtn = ttk.Button(midiPanel, text='(0) Refresh', command=RefreshMidi)
refreshBtn.pack(fill='x', expand='false')

actionPanel = ttk.Frame(root)
actionPanel.pack(fill='both', expand='true')
uploadPanel = ttk.Frame(actionPanel)
uploadPanel.pack(side='top',fill='both', expand='true')
############################################################################################ Upload File Tree
ttk.Label(uploadPanel, text='\n Select Patch From File:').pack(side='top')
# File tree setup!
patchFiles = ttk.Treeview(uploadPanel, height=12, show=("tree"), columns=('Date'), displaycolumns='#all', selectmode='browse')
patchFiles.pack(side='top',fill='both', expand='true')
patchFiles.tag_configure('folder', background='#445')
patchFiles.tag_configure('patch', background='#334')
patchFiles.column('Date')
# scroll
patchFilesBar = ttk.Scrollbar(patchFiles, orient='vertical', command=patchFiles.yview)
patchFilesBar.pack(side='right',fill='y')

# And uploader
ttk.Button(uploadPanel, text='Upload to DX...', command=UploadSelected).pack(side='bottom',fill='x', expand='false')

downloadPanel = ttk.Frame(actionPanel)
downloadPanel.pack(side='bottom',fill='x', expand='false')
############################################################################################# Download Dialog
ttk.Label(downloadPanel, text='\n Current Patch:').pack(side='top')
ttk.Button(downloadPanel, text='Save As...', command=RequestPatch).pack(fill='x', expand='false')
ttk.Label(downloadPanel, text='\n Name Utility:').pack(side='top')
ttk.Button(downloadPanel, text='Get Name', command=GetPatchName).pack(side='left',fill='x', expand='false')
ttk.Button(downloadPanel, text='Set Name (10 chars)', command=SetPatchName).pack(side='right',fill='x', expand='false')

easyPatchName = StringVar()
patchNameEntry = ttk.Entry(downloadPanel, textvariable=easyPatchName)
patchNameEntry.pack(side='right',fill='x',expand='true')
easyPatchName.set('Dyna Choir')


# Done
RefreshFiles()
root.mainloop()



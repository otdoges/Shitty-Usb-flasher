import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import shutil
import platform
import psutil
import threading
import time

class HackintoshFlasher(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Hackintosh USB Flasher")
        self.geometry("700x500")
        self.configure(bg='#f0f0f0')

        # Main container
        self.main_frame = ttk.Frame(self, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # USB Drive selection with size info
        ttk.Label(self.main_frame, text="Select USB Drive:").grid(row=0, column=0, sticky=tk.W)
        self.usb_drives_combo = ttk.Combobox(self.main_frame, state="readonly", width=50)
        self.usb_drives_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(self.main_frame, text="Refresh", command=self.refresh_usb_drives).grid(row=0, column=2, padx=5)

        # macOS Image selection
        ttk.Label(self.main_frame, text="Select macOS Image:").grid(row=1, column=0, sticky=tk.W)
        self.image_path = tk.StringVar()
        ttk.Entry(self.main_frame, textvariable=self.image_path, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(self.main_frame, text="Browse", command=self.browse_image).grid(row=1, column=2, padx=5)

        # EFI selection
        ttk.Label(self.main_frame, text="Select EFI Folder:").grid(row=2, column=0, sticky=tk.W)
        self.efi_path = tk.StringVar()
        ttk.Entry(self.main_frame, textvariable=self.efi_path, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        ttk.Button(self.main_frame, text="Browse", command=self.browse_efi).grid(row=2, column=2, padx=5)

        # Progress frame
        progress_frame = ttk.LabelFrame(self.main_frame, text="Progress", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20)

        # Progress bar
        self.progress = ttk.Progressbar(progress_frame, length=600, mode='determinate')
        self.progress.grid(row=0, column=0, pady=10, sticky=(tk.W, tk.E))

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, pady=5)

        # Buttons frame
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        # Flash button
        self.flash_button = ttk.Button(button_frame, text="Flash USB", command=self.start_flashing, style='Accent.TButton')
        self.flash_button.grid(row=0, column=0, padx=5)

        # Cancel button
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_operation, state='disabled')
        self.cancel_button.grid(row=0, column=1, padx=5)

        # Initialize variables
        self.flashing_thread = None
        self.cancel_flag = False

        # Start USB detection
        self.refresh_usb_drives()

    def get_usb_drives(self):
        usb_drives = []        try:
            # Get removable drives using psutil
            for partition in psutil.disk_partitions():
                try:
                    if 'removable' in partition.opts.lower():
                        usage = psutil.disk_usage(partition.mountpoint)
                        size_gb = usage.total / (1024**3)
                        
                        # Filter drives between 4GB and 128GB
                        if 4 <= size_gb <= 128:
                            drive_letter = partition.device.rstrip('\\')
                            drive_info = f"{drive_letter} ({size_gb:.1f} GB)"
                            usb_drives.append((drive_info, drive_letter))
                except Exception:
                    continue
                
        except Exception as e:
            print(f"Error detecting USB drives: {e}")
        return usb_drives
    
    def flash_usb(self):
        try:
            # Get drive letter from selection
            selected_drive = self.usb_drives_combo.get().split()[0]
            iso_path = self.image_path.get()
            efi_path = self.efi_path.get()
    
            # Step 1: Format the drive
            self.update_progress(5, "Preparing disk...")
            format_cmd = f'format {selected_drive} /fs:fat32 /q /y'
            subprocess.run(format_cmd, shell=True, capture_output=True)
    
            # Create diskpart script
            with open("diskpart.txt", "w") as f:
                f.write(f"select disk {selected_drive[-1]}\n")  # Get last character of disk number
                f.write("clean\n")
                f.write("create partition primary\n")
                f.write("format fs=fat32 quick\n")
                f.write("active\n")
                f.write("assign\n")
                f.write("exit\n")

            subprocess.run(clean_cmd, shell=True, check=True)

            # Step 2: Copy ISO contents using optimized buffer
            self.update_progress(20, "Copying ISO contents...")
            buffer_size = 8 * 1024 * 1024  # 8MB buffer for faster copying
            
            total_size = os.path.getsize(iso_path)
            copied_size = 0

            with open(iso_path, 'rb') as src:
                with open(f"{selected_drive}", 'wb', buffering=buffer_size) as dst:
                    while True:
                        if self.cancel_flag:
                            raise Exception("Operation cancelled by user")
                        
                        chunk = src.read(buffer_size)
                        if not chunk:
                            break
                        dst.write(chunk)
                        
                        copied_size += len(chunk)
                        progress = (copied_size / total_size) * 60
                        self.update_progress(20 + progress, f"Copying ISO... {copied_size//(1024*1024)}MB/{total_size//(1024*1024)}MB")

            # Step 3: Copy EFI files
            self.update_progress(80, "Setting up EFI...")
            efi_dest = f"{selected_drive}\\EFI"
            shutil.copytree(efi_path, efi_dest, dirs_exist_ok=True)

            if not self.cancel_flag:
                self.update_progress(100, "Flash completed successfully!")
                messagebox.showinfo("Success", "USB flashing completed successfully!")
            
        except Exception as e:
            self.update_progress(0, f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            if os.path.exists("diskpart.txt"):
                os.remove("diskpart.txt")
            self.flash_button.configure(state='normal')
            self.cancel_button.configure(state='disabled')

    def refresh_usb_drives(self):
        drives = self.get_usb_drives()
        if drives:
            self.usb_drives_combo['values'] = [drive[0] for drive in drives]
            self.usb_drives_combo.set(drives[0][0])
        else:
            self.usb_drives_combo['values'] = ["No USB drives detected"]
            self.usb_drives_combo.set("No USB drives detected")

    def browse_image(self):
        filename = filedialog.askopenfilename(
            title="Select ISO Image",
            filetypes=[("ISO files", "*.iso")]  # Only allowing ISO files now
        )
        if filename:
            self.image_path.set(filename)

    def browse_efi(self):
        directory = filedialog.askdirectory(title="Select EFI Folder")
        if directory:
            self.efi_path.set(directory)

    def validate_inputs(self):
        if self.usb_drives_combo.get() == "No USB drives detected":
            messagebox.showerror("Error", "No USB drive detected")
            return False
        if not self.image_path.get():
            messagebox.showerror("Error", "Please select a macOS image")
            return False
        if not self.efi_path.get():
            messagebox.showerror("Error", "Please select an EFI folder")
            return False
        if not os.path.exists(self.image_path.get()):
            messagebox.showerror("Error", "Selected macOS image does not exist")
            return False
        if not os.path.exists(self.efi_path.get()):
            messagebox.showerror("Error", "Selected EFI folder does not exist")
            return False
        return True

    def start_flashing(self):
        if not self.validate_inputs():
            return

        self.cancel_flag = False
        self.flash_button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        
        self.flashing_thread = threading.Thread(target=self.flash_usb)
        self.flashing_thread.start()

    def cancel_operation(self):
        self.cancel_flag = True
        self.status_var.set("Cancelling operation...")

    def update_progress(self, value, status):
        self.progress['value'] = value
        self.status_var.set(status)
        self.update()

if __name__ == "__main__":
    app = HackintoshFlasher()
    app.mainloop()
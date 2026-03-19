import streamlit as st
import pandas as pd
import qrcode
import os
import io
import base64
from datetime import datetime
from PIL import Image
import json
import csv
import time

# Page configuration
st.set_page_config(
    page_title="HIT Asset Verification System",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create data directory if it doesn't exist
os.makedirs("data", exist_ok=True)
os.makedirs("qr_codes", exist_ok=True)

class AssetManager:
    def __init__(self):
        self.laptops_file = "data/laptops.csv"
        self.logs_file = "data/verification_logs.csv"
        self.users_file = "data/users.csv"
        self.action_logs_file = "data/action_logs.csv"
        self.notifications_file = "data/notifications.csv"
        self.initialize_files()
    
    def initialize_files(self):
        """Create CSV files with headers if they don't exist"""
        # Laptops file
        if not os.path.exists(self.laptops_file):
            with open(self.laptops_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'student_name', 'student_id', 'laptop_serial', 
                    'laptop_brand', 'laptop_model', 'color', 'contact_number',
                    'registration_date', 'qr_code_data', 'qr_code_path', 'status'
                ])
        
        # Verification logs file
        if not os.path.exists(self.logs_file):
            with open(self.logs_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'student_id', 'student_name', 'laptop_serial',
                    'verification_type', 'location', 'verified_by', 'status'
                ])
        
        # User credentials file
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['username', 'password', 'full_name', 'role'])
                # Default admin: guard1 / password123
                writer.writerow(['admin', 'admin123', 'System Administrator', 'Admin'])
                writer.writerow(['guard1', 'password123', 'John Doe (Senior Guard)', 'Security'])
                writer.writerow(['guard2', 'hit2024', 'Jane Smith', 'Security'])
        
        # Action logs file
        if not os.path.exists(self.action_logs_file):
            with open(self.action_logs_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'user', 'action', 'target_id', 'details'])

        # Notifications file
        if not os.path.exists(self.notifications_file):
            with open(self.notifications_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'student_id', 'message', 'status'])
        
        # Migration: Add status column to existing laptops file if missing
        if os.path.exists(self.laptops_file):
            df = pd.read_csv(self.laptops_file)
            if 'status' not in df.columns:
                df['status'] = 'Active'
                df.to_csv(self.laptops_file, index=False)
    
    def register_laptop(self, student_data):
        """Register a new laptop and generate QR code"""
        try:
            # Check if student ID or serial already exists
            existing_data = self.get_all_laptops()
            if not existing_data.empty:
                # Check laptop serial
                if student_data['laptop_serial'] in existing_data['laptop_serial'].values:
                    existing_device = existing_data[existing_data['laptop_serial'] == student_data['laptop_serial']].iloc[0]
                    if existing_device['student_id'] != student_data['student_id']:
                        # Flag as confiscated if registered to someone else
                        self.update_laptop_status(existing_device['student_id'], student_data['laptop_serial'], "Confiscated")
                        self.log_action(st.session_state.user['username'] if 'user' in st.session_state else 'System', 
                                        "Flagged - Attempted Duplicate", student_data['laptop_serial'], 
                                        f"Attempt by {student_data['student_id']} on {existing_device['student_id']}'s device")
                        return "CONFISCATED", f"CRITICAL: Serial {student_data['laptop_serial']} is already registered to student {existing_device['student_id']}. Device has been FLAG AS CONFISCATED for investigation.", None
                    return False, "Laptop serial number already registered", None
                
                # Check registration limit (max 5 gadgets per individual)
                student_devices = existing_data[existing_data['student_id'] == student_data['student_id']]
                if len(student_devices) >= 5:
                    return False, f"Maximum limit reached: {student_data['student_id']} already has 5 registered gadgets.", None
            
            # Generate QR code data
            qr_data = {
                "student_name": student_data['student_name'],
                "student_id": student_data['student_id'],
                "laptop_serial": student_data['laptop_serial'],
                "laptop_brand": student_data['laptop_brand'],
                "laptop_model": student_data['laptop_model'],
                "registration_date": student_data['registration_date'],
                "institution": "HIT"
            }
            qr_data_str = json.dumps(qr_data)
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=12,
                border=4,
            )
            qr.add_data(qr_data_str)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR code
            qr_filename = f"{student_data['student_id']}_{student_data['laptop_serial']}.png"
            qr_path = os.path.join("qr_codes", qr_filename)
            qr_img.save(qr_path)
            
            # Add to CSV
            new_row = {
                'student_name': student_data['student_name'],
                'student_id': student_data['student_id'],
                'laptop_serial': student_data['laptop_serial'],
                'laptop_brand': student_data['laptop_brand'],
                'laptop_model': student_data['laptop_model'],
                'color': student_data['color'],
                'contact_number': student_data['contact_number'],
                'registration_date': student_data['registration_date'],
                'qr_code_data': qr_data_str,
                'qr_code_path': qr_path,
                'status': 'Active'
            }
            
            # Append to CSV
            df = self.get_all_laptops()
            new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            new_df.to_csv(self.laptops_file, index=False)
            
            # Log the registration action
            self.log_action(st.session_state.user['username'] if 'user' in st.session_state else 'System', 
                            "Register Device", student_data['laptop_serial'], f"Registered to {student_data['student_id']}")

            # Convert PIL Image to bytes for Streamlit display
            img_bytes = io.BytesIO()
            qr_img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            return True, qr_path, img_bytes
            
        except Exception as e:
            return False, str(e), None
    
    def get_all_laptops(self):
        """Get all registered laptops"""
        try:
            return pd.read_csv(self.laptops_file)
        except:
            return pd.DataFrame()
    
    def search_laptops(self, search_term):
        """Search laptops by any field"""
        df = self.get_all_laptops()
        if df.empty:
            return df
        
        mask = (
            df['student_name'].str.contains(search_term, case=False, na=False) |
            df['student_id'].str.contains(search_term, case=False, na=False) |
            df['laptop_serial'].str.contains(search_term, case=False, na=False) |
            df['laptop_brand'].str.contains(search_term, case=False, na=False) |
            df['contact_number'].str.contains(search_term, case=False, na=False)
        )
        return df[mask]
    
    def verify_laptop(self, qr_data, location="Main Gate", verified_by="Security Guard"):
        """Verify laptop ownership using QR code data"""
        try:
            # Parse QR data
            qr_info = json.loads(qr_data)
            student_id = qr_info.get('student_id')
            laptop_serial = qr_info.get('laptop_serial')
            
            # Find laptop in database
            df = self.get_all_laptops()
            if df.empty:
                return False, "No devices registered in system"
            
            laptop = df[
                (df['student_id'] == student_id) & 
                (df['laptop_serial'] == laptop_serial)
            ]
            
            if laptop.empty:
                # Log failed attempt
                self.log_verification(
                    datetime.now().isoformat(),
                    student_id,
                    qr_info.get('student_name', 'Unknown'),
                    laptop_serial,
                    "QR Scan",
                    location,
                    verified_by,
                    "FAILED - Not Registered"
                )
                return False, "Device not registered in system"
            
            laptop_data = laptop.iloc[0]
            
            # Check for lost/stolen status
            if laptop_data.get('status') == 'Lost/Stolen':
                # Log detection of stolen device
                self.log_verification(
                    datetime.now().isoformat(),
                    student_id,
                    laptop_data['student_name'],
                    laptop_serial,
                    "QR Scan",
                    location,
                    verified_by,
                    "STOLEN DEVICE DETECTED"
                )
                return "STOLEN", laptop_data

            # Log successful verification
            self.log_verification(
                datetime.now().isoformat(),
                student_id,
                laptop_data['student_name'],
                laptop_serial,
                "QR Scan",
                location,
                verified_by,
                "SUCCESS"
            )
            
            return True, laptop_data
            
        except json.JSONDecodeError:
            return False, "Invalid QR code format"
        except Exception as e:
            return False, f"Verification error: {str(e)}"
    
    def log_verification(self, timestamp, student_id, student_name, laptop_serial, 
                        verification_type, location, verified_by, status):
        """Log verification attempts"""
        try:
            new_log = {
                'timestamp': timestamp,
                'student_id': student_id,
                'student_name': student_name,
                'laptop_serial': laptop_serial,
                'verification_type': verification_type,
                'location': location,
                'verified_by': verified_by,
                'status': status
            }
            
            # Read existing logs
            try:
                logs_df = pd.read_csv(self.logs_file)
            except:
                logs_df = pd.DataFrame()
            
            # Append new log
            new_logs_df = pd.concat([logs_df, pd.DataFrame([new_log])], ignore_index=True)
            new_logs_df.to_csv(self.logs_file, index=False)
            
        except Exception as e:
            print(f"Error logging verification: {e}")
            
    def update_laptop_status(self, student_id, laptop_serial, new_status):
        """Update the status of a registered laptop"""
        try:
            df = self.get_all_laptops()
            if df.empty:
                return False, "No devices registered"
            
            mask = (df['student_id'] == student_id) & (df['laptop_serial'] == laptop_serial)
            if not df[mask].any().any():
                return False, "Device not found"
            
            df.loc[mask, 'status'] = new_status
            df.to_csv(self.laptops_file, index=False)
            
            # Auto-notify student if status change is significant
            if new_status in ["Active", "Found", "Pending Verification"]:
                self.add_notification(student_id, f"Your device (Serial: {laptop_serial}) status has been updated to {new_status}. Please visit the exit point with your ID if recovery is needed.")
            
            # Log the status change
            self.log_action(st.session_state.user['username'] if 'user' in st.session_state else 'System', 
                            "Status Change", laptop_serial, f"Changed to {new_status} for student {student_id}")

            return True, f"Status updated to {new_status}"
        except Exception as e:
            return False, str(e)

    def get_notifications(self, student_id):
        """Get notifications for a specific student"""
        try:
            if not os.path.exists(self.notifications_file):
                return pd.DataFrame()
            df = pd.read_csv(self.notifications_file)
            return df[df['student_id'] == student_id].sort_values(by='timestamp', ascending=False)
        except:
            return pd.DataFrame()

    def add_notification(self, student_id, message):
        """Add a notification for a student"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_notif = {
                'timestamp': timestamp,
                'student_id': student_id,
                'message': message,
                'status': 'Unread'
            }
            try:
                df = pd.read_csv(self.notifications_file)
            except:
                df = pd.DataFrame(columns=['timestamp', 'student_id', 'message', 'status'])
            
            df = pd.concat([df, pd.DataFrame([new_notif])], ignore_index=True)
            df.to_csv(self.notifications_file, index=False)
            return True
        except Exception as e:
            print(f"Error adding notification: {e}")
            return False

    def mark_notifications_read(self, student_id):
        """Mark all notifications as read for a student"""
        try:
            df = pd.read_csv(self.notifications_file)
            df.loc[df['student_id'] == student_id, 'status'] = 'Read'
            df.to_csv(self.notifications_file, index=False)
            return True
        except:
            return False

    def authenticate(self, username, password):
        """Authenticate user credentials"""
        try:
            users_df = pd.read_csv(self.users_file)
            user = users_df[(users_df['username'] == username) & (users_df['password'] == password)]
            if not user.empty:
                return True, user.iloc[0].to_dict()
            return False, "Invalid username or password"
        except Exception as e:
            return False, f"Authentication error: {str(e)}"

    def get_all_users(self):
        """Get all registered users"""
        try:
            return pd.read_csv(self.users_file)
        except:
            return pd.DataFrame()

    def register_user(self, user_data):
        """Register a new system user"""
        try:
            users_df = self.get_all_users()
            if not users_df.empty and user_data['username'] in users_df['username'].values:
                return False, "Username already exists"
            
            new_row = pd.DataFrame([user_data])
            users_df = pd.concat([users_df, new_row], ignore_index=True)
            users_df.to_csv(self.users_file, index=False)
            
            # Log the action
            self.log_action(st.session_state.user['username'] if 'user' in st.session_state else 'System', 
                            "Register User", user_data['username'], f"New {user_data['role']} added")
            return True, "User registered successfully"
        except Exception as e:
            return False, str(e)

    def log_action(self, user, action, target_id, details):
        """Log administrator actions"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_log = {
                'timestamp': timestamp,
                'user': user,
                'action': action,
                'target_id': target_id,
                'details': details
            }
            try:
                logs_df = pd.read_csv(self.action_logs_file)
            except:
                logs_df = pd.DataFrame(columns=['timestamp', 'user', 'action', 'target_id', 'details'])
            
            new_logs_df = pd.concat([logs_df, pd.DataFrame([new_log])], ignore_index=True)
            new_logs_df.to_csv(self.action_logs_file, index=False)
        except Exception as e:
            print(f"Error logging action: {e}")

    def get_action_logs(self):
        """Get all system action logs"""
        try:
            return pd.read_csv(self.action_logs_file)
        except:
            return pd.DataFrame()

    def get_verification_logs(self):
        """Get all verification logs"""
        try:
            logs_df = pd.read_csv(self.logs_file)
            # Convert timestamp to datetime and format as string for display
            if not logs_df.empty and 'timestamp' in logs_df.columns:
                logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            return logs_df
        except:
            return pd.DataFrame()
    
    def get_statistics(self):
        """Get system statistics"""
        laptops_df = self.get_all_laptops()
        logs_df = self.get_verification_logs()
        
        stats = {
            'total_devices': len(laptops_df),
            'verified_today': 0,
            'total_verifications': len(logs_df),
            'successful_verifications': 0,
            'failed_verifications': 0,
            'stolen_reported': len(laptops_df[laptops_df['status'] == 'Lost/Stolen']) if 'status' in laptops_df.columns else 0,
            'stolen_detected': len(logs_df[logs_df['status'] == 'STOLEN DEVICE DETECTED']) if not logs_df.empty else 0
        }
        
        if not logs_df.empty:
            today = datetime.now().date()
            # Convert back to datetime for date comparison
            logs_df_temp = logs_df.copy()
            logs_df_temp['timestamp'] = pd.to_datetime(logs_df_temp['timestamp'])
            today_logs = logs_df_temp[logs_df_temp['timestamp'].dt.date == today]
            
            stats['verified_today'] = len(today_logs)
            stats['successful_verifications'] = len(logs_df[logs_df['status'] == 'SUCCESS'])
            stats['failed_verifications'] = len(logs_df[logs_df['status'].str.startswith('FAILED')])
        
        return stats

def convert_to_excel(df):
    """Convert DataFrame to Excel format with error handling"""
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Registered_Devices')
        return output.getvalue()
    except ImportError:
        # Fallback: return None if xlsxwriter is not available
        return None

def main():
    # PREMIUM UI DESIGN SYSTEM
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

    /* Global styles */
    .stApp {
        font-family: 'Outfit', sans-serif;
        background-color: #f8fafc !important;
        background-attachment: fixed !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(34, 211, 238, 0.1) 0px, transparent 50%),
            radial-gradient(at 100% 0%, rgba(59, 130, 246, 0.08) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(34, 211, 238, 0.08) 0px, transparent 50%),
            radial-gradient(at 0% 100%, rgba(15, 23, 42, 0.05) 0px, transparent 50%) !important;
    }

    .stApp::before {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        opacity: 0.02;
        pointer-events: none;
        z-index: 0;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
    }

    /* Main background and text */
    .main {
        background-color: transparent;
    }

    /* Visibility and Contrast Fixes */
    [data-testid="stWidgetLabel"] p, 
    [data-testid="stMarkdownContainer"] p,
    .stMarkdown p, label {
        color: #1e293b !important;
        font-weight: 600 !important;
    }

    h2, h3 {
        color: #0f172a !important;
    }
    
    /* Ensure metric card headers stay readable */
    .metric-card h2, .metric-card h3 {
        color: inherit !important;
    }
    
    /* Headers */
    .main-header {
        font-size: 2.8rem;
        color: #f1f5f9;
        text-align: center;
        margin-bottom: 2.5rem;
        font-weight: 700;
        padding: 2.5rem;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        letter-spacing: -0.025em;
        text-transform: uppercase;
    }
    
    /* Content Area Background for Readability */
    [data-testid="stVerticalBlock"] > div:has(div.sub-header), 
    [data-testid="stVerticalBlock"] > div:has(div.info-box),
    .stTabs, .stForm {
        background: rgba(255, 255, 255, 0.82) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        padding: 2rem !important;
        border-radius: 1.5rem !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.5) !important;
        margin-bottom: 2rem !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease !important;
    }
    
    .sub-header {
        font-size: 2rem !important;
        color: #0f172a !important;
        margin: 1rem 0 1.5rem 0 !important;
        font-weight: 700 !important;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .sub-header::after {
        content: '';
        flex: 1;
        height: 3px;
        background: linear-gradient(to right, #22d3ee, transparent);
        margin-left: 1rem;
        border-radius: 2px;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        padding: 1.5rem !important;
    }
    
    /* Success Box - Cyan theme */
    .success-box {
        padding: 1.5rem;
        background: rgba(34, 211, 238, 0.08);
        border-left: 4px solid #22d3ee;
        border-radius: 0.75rem;
        color: #083344;
        margin: 1.5rem 0;
        font-weight: 500;
    }
    
    /* Error Box - Rose theme */
    .error-box {
        padding: 1.5rem;
        background: rgba(244, 63, 94, 0.08);
        border-left: 4px solid #f43f5e;
        border-radius: 0.75rem;
        color: #4c0519;
        margin: 1.5rem 0;
        font-weight: 500;
    }
    
    /* Info Box - Slate theme */
    .info-box {
        padding: 1.5rem;
        background: rgba(148, 163, 184, 0.08);
        border-left: 4px solid #94a3b8;
        border-radius: 0.75rem;
        color: #1e293b;
        margin: 1.5rem 0;
        font-weight: 500;
    }
    
    /* Metric Cards - Premium gradients */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 2.25rem 1.5rem;
        border-radius: 1.5rem;
        color: #f8fafc;
        text-align: center;
        border: 1px solid rgba(34, 211, 238, 0.2);
        box-shadow: 0 15px 30px -10px rgba(0, 0, 0, 0.3);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        overflow: hidden;
    }

    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: radial-gradient(circle at top right, rgba(34, 211, 238, 0.1), transparent);
        pointer-events: none;
    }

    .metric-card:hover {
        transform: translateY(-10px) scale(1.02);
        box-shadow: 0 30px 60px -15px rgba(0, 0, 0, 0.4);
        border-color: #22d3ee;
    }

    .metric-card h3 {
        font-size: 1rem;
        font-weight: 500;
        color: #94a3b8;
        margin-bottom: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .metric-card h2 {
        font-size: 2.75rem;
        font-weight: 800;
        color: #22d3ee;
        margin: 0;
        text-shadow: 0 0 20px rgba(34, 211, 238, 0.3);
    }
    
    /* Buttons - Modern styling */
    .stButton button {
        border-radius: 0.75rem !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 700 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: none !important;
        width: 100% !important;
        text-transform: uppercase !important;
        letter-spacing: 0.025em !important;
    }
    
    /* Primary buttons */
    .stButton button[kind="primary"], .stButton button:first-child {
        background: linear-gradient(90deg, #06b6d4 0%, #3b82f6 100%) !important;
        color: white !important;
        box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.4) !important;
    }
    
    .stButton button:first-child:hover {
        box-shadow: 0 20px 25px -5px rgba(59, 130, 246, 0.5) !important;
        transform: translateY(-3px) !important;
        filter: brightness(1.1) !important;
    }
    
    /* Sidebar Navigation icons and links */
    .sidebar-header {
        color: #22d3ee;
        font-size: 1.5rem;
        font-weight: 800;
        text-align: center;
        padding: 1.5rem;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 1rem;
        margin-bottom: 2rem;
        border: 1px solid rgba(34, 211, 238, 0.3);
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    
    /* Form elements */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        background-color: rgba(255, 255, 255, 0.9) !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 0.75rem !important;
        padding: 0.85rem !important;
        color: #0f172a !important;
        font-weight: 500 !important;
    }
    
    .stTextInput input:focus {
        border-color: #22d3ee !important;
        box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.2) !important;
    }

    /* Visibility and Contrast for placeholders and widgets */
    ::placeholder {
        color: #64748b !important;
        opacity: 1 !important;
        -webkit-text-fill-color: #64748b !important;
    }

    .stTextInput input::placeholder, 
    .stTextArea textarea::placeholder {
        color: #64748b !important;
        opacity: 1 !important;
    }

    /* Fix Date Input, Number Input, and other widget backgrounds */
    .stDateInput div[data-baseweb="input"],
    .stNumberInput div[data-baseweb="input"],
    .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(255, 255, 255, 0.9) !important;
        border-radius: 0.75rem !important;
        color: #0f172a !important;
    }
    
    [data-baseweb="input"] {
        background-color: rgba(255, 255, 255, 0.9) !important;
        color: #0f172a !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
        background-color: transparent;
        padding: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 0.75rem;
        padding: 0.85rem 1.75rem;
        color: #475569;
        font-weight: 700;
        border: 1px solid #e2e8f0;
        transition: all 0.2s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #0f172a !important;
        color: #22d3ee !important;
        border-color: #22d3ee !important;
        transform: translateY(-2px);
    }
    
    /* Glass floating elements background */
    .glass-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: -1;
        overflow: hidden;
        background: radial-gradient(circle at 50% 50%, #f8fafc 0%, #e2e8f0 100%);
    }

    .glass-element {
        position: absolute;
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(15px) !important;
        -webkit-backdrop-filter: blur(15px) !important;
        border: 1px solid rgba(255, 255, 255, 0.2);
        animation: float-bg 35s infinite ease-in-out;
        opacity: 0.8;
        box-shadow: 0 0 40px rgba(34, 211, 238, 0.05);
    }

    .glass-sphere {
        border-radius: 50%;
    }

    .glass-cube {
        border-radius: 20%;
        transform: rotate(45deg);
    }

    @keyframes float-bg {
        0%, 100% { transform: translate(0, 0) rotate(0deg); }
        33% { transform: translate(40px, -60px) rotate(15deg); }
        66% { transform: translate(-30px, 30px) rotate(-15deg); }
    }

    .delay-1 { animation-delay: -3s; }
    .delay-2 { animation-delay: -7s; }
    .delay-3 { animation-delay: -11s; }
    .delay-4 { animation-delay: -15s; }

    /* Sidebar Navigation spacing */
    [data-testid="stSidebar"] .stButton {
        margin-bottom: 1rem !important;
    }

    [data-testid="stSidebar"] .stButton button {
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 0.75rem 1rem !important;
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        transform: translateX(5px) !important;
        background: rgba(34, 211, 238, 0.1) !important;
        border: 1px solid #22d3ee !important;
    }

    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="glass-container">
        <div class="glass-element glass-sphere delay-1" style="width: 400px; height: 400px; top: -150px; right: -150px;"></div>
        <div class="glass-element glass-cube delay-2" style="width: 250px; height: 250px; bottom: 15%; left: -80px;"></div>
        <div class="glass-element glass-sphere delay-3" style="width: 200px; height: 200px; top: 35%; right: 15%; background: rgba(59, 130, 246, 0.03);"></div>
        <div class="glass-element glass-cube delay-4" style="width: 150px; height: 150px; top: 15%; left: 25%; opacity: 0.4;"></div>
        <div class="glass-element glass-sphere delay-1" style="width: 500px; height: 500px; bottom: -200px; right: 20%; opacity: 0.02;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="main-header">🛡️ HIT ASSET VERIFICATION</div>', unsafe_allow_html=True)
    
    # Initialize asset manager
    asset_manager = AssetManager()
    
    # Session state initialization
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'role_selection' not in st.session_state:
        st.session_state.role_selection = None
    
    # Landing Page
    if not st.session_state.logged_in and st.session_state.role_selection is None:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h2 style="color: #0f172a;">Welcome to HIT Asset Verification System</h2>
            <p style="color: #64748b; font-size: 1.2rem;">Please select your portal to continue</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="metric-card" style="cursor: pointer; height: 100%;">
                <h2 style="font-size: 4rem;">🎓</h2>
                <h3>Student</h3>
                <p style="color: #94a3b8; font-size: 0.9rem;">Register devices, report loss, and view QR codes</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Access Student Portal", use_container_width=True, key="btn_student"):
                st.session_state.role_selection = "Student"
                st.rerun()
                
        with col2:
            st.markdown("""
            <div class="metric-card" style="cursor: pointer; height: 100%;">
                <h2 style="font-size: 4rem;">🛡️</h2>
                <h3>Security</h3>
                <p style="color: #94a3b8; font-size: 0.9rem;">Verify devices and manage security logs</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Access Security Portal", use_container_width=True, key="btn_security"):
                st.session_state.role_selection = "Security"
                st.rerun()
                
        with col3:
            st.markdown("""
            <div class="metric-card" style="cursor: pointer; height: 100%;">
                <h2 style="font-size: 4rem;">⚙️</h2>
                <h3>Admin</h3>
                <p style="color: #94a3b8; font-size: 0.9rem;">Full system management and user control</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Access Admin Portal", use_container_width=True, key="btn_admin"):
                st.session_state.role_selection = "Admin"
                st.rerun()
        return

    # Login Page for selected role
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(f'<div class="info-box" style="text-align: center;">', unsafe_allow_html=True)
            st.subheader(f"🛡️ {st.session_state.role_selection} Login")
            
            if st.session_state.role_selection == "Student":
                st.info("💡 Students can use their Student ID as username and password for first-time login.")
            
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("⬅️ Back", use_container_width=True):
                    st.session_state.role_selection = None
                    st.rerun()
            with col_b2:
                if st.button("🔐 Login", use_container_width=True):
                    # Check if student exists in laptops.csv but not users.csv (simple auto-registration for demo)
                    success, user_data = asset_manager.authenticate(username, password)
                    
                    # Student special case: if not in users.csv, check if they have registered laptops
                    if not success and st.session_state.role_selection == "Student":
                        laptops_df = asset_manager.get_all_laptops()
                        if not laptops_df.empty and username.upper() in laptops_df['student_id'].values:
                            # For demo purposes, we'll allow login if student_id matches and password is same as ID
                            if password == username:
                                student_info = laptops_df[laptops_df['student_id'] == username.upper()].iloc[0]
                                user_data = {
                                    'username': username.upper(),
                                    'full_name': student_info['student_name'],
                                    'role': 'Student'
                                }
                                success = True
                    
                    if success:
                        if user_data['role'] != st.session_state.role_selection and not (user_data['role'] == 'Admin' and st.session_state.role_selection == 'Security'):
                             st.error(f"❌ Access Denied: You do not have {st.session_state.role_selection} privileges.")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.user = user_data
                            asset_manager.log_action(username, "Login", "System", f"Successful {user_data['role']} login")
                            st.rerun()
                    else:
                        st.error(f"❌ {user_data}")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # Sidebar navigation with custom styling
    st.sidebar.markdown(f"""
    <div class="info-box" style="padding: 10px; margin-bottom: 10px;">
        👤 <b>User:</b> {st.session_state.user['full_name']}<br>
        🛡️ <b>Role:</b> {st.session_state.user['role']}
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        asset_manager.log_action(st.session_state.user['username'], "Logout", "System", "Manual logout")
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.role_selection = None
        st.rerun()
    
    # Sidebar navigation with custom styling
    st.sidebar.markdown('<div class="sidebar-header">🏢 HIT Navigation</div>', unsafe_allow_html=True)
    
    # Define menus based on role
    role = st.session_state.user['role']
    
    if role == 'Admin':
        menu_options = [
            "🏠 Dashboard",
            "📝 Register New Device", 
            "🔍 Verify Ownership",
            "📊 View All Devices",
            "📋 Verification Logs",
            "📜 System Action Logs",
            "👤 User Management",
            "🔄 Manage Device Status",
            "🚨 Report Lost Device",
            "⚙️ System Settings"
        ]
    elif role == 'Security':
        menu_options = [
            "🏠 Dashboard",
            "🔍 Verify Ownership",
            "📊 View All Devices",
            "📋 Verification Logs",
            "🔄 Manage Device Status"
        ]
    elif role == 'Student':
        # Get notification count
        notifs = asset_manager.get_notifications(st.session_state.user['username'])
        unread_count = len(notifs[notifs['status'] == 'Unread']) if not notifs.empty else 0
        notif_label = f"🔔 Notifications ({unread_count})" if unread_count > 0 else "🔔 Notifications"
        
        menu_options = [
            "🏠 Dashboard",
            "📝 Register New Device",
            "💻 My Devices",
            "🚨 Report Lost Device",
            notif_label
        ]
        
    if 'choice' not in st.session_state:
        st.session_state.choice = "🏠 Dashboard"
        
    for option in menu_options:
        # Handle dynamic labels for choice matching
        display_option = option
        choice_key = option
        if "🔔 Notifications" in option:
            choice_key = "🔔 Notifications"
            
        if st.sidebar.button(display_option, use_container_width=True):
            st.session_state.choice = choice_key
            st.rerun()
            
    choice = st.session_state.choice
    
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    
    # Dashboard
    if choice == "🏠 Dashboard":
        st.markdown(f'<div class="sub-header">{role} Dashboard</div>', unsafe_allow_html=True)
        
        if role == 'Student':
            # Student specific dashboard
            student_id = st.session_state.user['username']
            df = asset_manager.get_all_laptops()
            my_devices = df[df['student_id'] == student_id] if not df.empty else pd.DataFrame()
            
            stats = {
                'total_my_devices': len(my_devices),
                'active_devices': len(my_devices[my_devices['status'] == 'Active']) if not my_devices.empty else 0,
                'lost_reported': len(my_devices[my_devices['status'] == 'Lost/Stolen']) if not my_devices.empty else 0
            }
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f'<div class="metric-card"><h3>My Devices</h3><h2>{stats["total_my_devices"]}</h2></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #10b981 0%, #065f46 100%);"><h3>Active</h3><h2>{stats["active_devices"]}</h2></div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div class="metric-card" style="background: linear-gradient(135deg, #ef4444 0%, #991b1b 100%);"><h3>Lost</h3><h2>{stats["lost_reported"]}</h2></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("🔔 Recent Notifications")
            notifs = asset_manager.get_notifications(student_id)
            if not notifs.empty:
                for _, notif in notifs.head(3).iterrows():
                    style = "background: rgba(34, 211, 238, 0.1); border-left: 4px solid #22d3ee;" if notif['status'] == 'Unread' else "background: white; border-left: 4px solid #94a3b8;"
                    st.markdown(f'''
                    <div style="padding: 1rem; margin-bottom: 0.5rem; border-radius: 0.5rem; {style}">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-weight: 600;">{notif['timestamp']}</span>
                            <span style="font-size: 0.8rem; color: #64748b;">{notif['status']}</span>
                        </div>
                        <div style="margin-top: 0.5rem;">{notif['message']}</div>
                    </div>
                    ''', unsafe_allow_html=True)
            else:
                st.info("No notifications yet.")
        else:
            # Statistics for Admin/Security
            stats = asset_manager.get_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Total Devices</h3>
                <h2>{stats['total_devices']}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Verified Today</h3>
                <h2>{stats['verified_today']}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Total Verifications</h3>
                <h2>{stats['total_verifications']}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            success_rate = (stats['successful_verifications'] / stats['total_verifications'] * 100) if stats['total_verifications'] > 0 else 0
            st.markdown(f"""
            <div class="metric-card">
                <h3>Success Rate</h3>
                <h2>{success_rate:.1f}%</h2>
            </div>
            """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
             st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #ef4444 0%, #991b1b 100%);">
                <h3>Devices Reported Stolen</h3>
                <h2>{stats['stolen_reported']}</h2>
            </div>
            """, unsafe_allow_html=True)
        with col2:
             st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #f59e0b 0%, #b45309 100%);">
                <h3>Stolen Devices Detected</h3>
                <h2>{stats['stolen_detected']}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Quick actions
      #  st.markdown("---")
       # st.markdown('<div class="sub-header">Quick Actions</div>', unsafe_allow_html=True)
        
        #col1, col2, col3 = st.columns(3)
        #with col1:
         #   if st.button("🚀 Register New Device", use_container_width=True):
          #      st.session_state.redirect = "register_laptop"
        
       # with col2:
        #    if st.button("🔍 Verify Device", use_container_width=True):
         #       st.session_state.redirect = "Verify Ownership"
        
        #with col3:
         #   if st.button("📊 View Reports", use_container_width=True):
          #      st.session_state.redirect = "View All Devices"
        
        # Recent activity
        st.markdown("---")
        st.markdown('<div class="sub-header">Recent Verifications</div>', unsafe_allow_html=True)
        
        logs_df = asset_manager.get_verification_logs()
        if not logs_df.empty:
            recent_logs = logs_df.tail(10)
            for _, log in recent_logs.iterrows():
                status_color = "🟢" if log['status'] == 'SUCCESS' else "🔴"
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{status_color} **{log['student_name']}** - {log['laptop_serial']} at {log['timestamp']}")
                with col2:
                    st.write(f"*{log['status']}*")
                st.markdown("---")
        else:
            st.markdown('<div class="info-box">No verification logs available yet.</div>', unsafe_allow_html=True)
    
    # Register New Device
    elif choice == "📝 Register New Device":
        st.markdown('<div class="sub-header">Device Registration</div>', unsafe_allow_html=True)
        
        # Initialize session state for registration data
        if 'registration_data' not in st.session_state:
            st.session_state.registration_data = None
        if 'qr_code_bytes' not in st.session_state:
            st.session_state.qr_code_bytes = None
        
        # If we have successful registration data, show the success section
        if st.session_state.registration_data is not None:
            student_data = st.session_state.registration_data
            qr_img_bytes = st.session_state.qr_code_bytes
            
            st.balloons()
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            st.success("🎉 Device Registered Successfully!")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("📋 Registration Details")
                st.write(f"**Student Name:** {student_data['student_name']}")
                st.write(f"**Student ID:** {student_data['student_id']}")
                st.write(f"**Contact:** {student_data['contact_number']}")
                st.write(f"**Device:** {student_data['laptop_brand']} {student_data['laptop_model']}")
                st.write(f"**Serial:** {student_data['laptop_serial']}")
                st.write(f"**Color:** {student_data['color']}")
                st.write(f"**Registered:** {student_data['registration_date']}")
            
            with col2:
                st.subheader("📷 QR Code")
                # Display the QR code from bytes
                st.image(qr_img_bytes, caption="Device QR Code", width=200)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Download buttons (outside the form)
            col1, col2, col3 = st.columns(3)
            with col1:
                # Download QR code - use the same bytes object
                st.download_button(
                    label="📥 Download QR Code",
                    data=qr_img_bytes.getvalue(),
                    file_name=f"HIT_{student_data['student_id']}_{student_data['laptop_serial']}.png",
                    mime="image/png",
                    use_container_width=True
                )
            
            with col2:
                # Generate registration receipt
                receipt = f"""
HIT ASSET REGISTRATION RECEIPT
==============================
Student: {student_data['student_name']}
ID: {student_data['student_id']}
Contact: {student_data['contact_number']}
Device: {student_data['laptop_brand']} {student_data['laptop_model']}
Serial: {student_data['laptop_serial']}
Color: {student_data['color']}
Registered: {student_data['registration_date']}

Keep this QR code securely attached to your device.
"""
                
                st.download_button(
                    label="📄 Download Receipt",
                    data=receipt,
                    file_name=f"HIT_Receipt_{student_data['student_id']}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col3:
                if st.button("🔄 Register Another Device", use_container_width=True):
                    st.session_state.registration_data = None
                    st.session_state.qr_code_bytes = None
                    st.rerun()
            
            st.markdown('<div class="info-box">💡 **Please print the QR code and attach it securely to your laptop.**</div>', unsafe_allow_html=True)
        
        else:
            # Show registration form
            with st.form("registration_form", clear_on_submit=True):
                st.subheader("🎓 Student Information")
                col1, col2 = st.columns(2)
                with col1:
                    student_name = st.text_input("Full Name *", value=st.session_state.user['full_name'] if role == 'Student' else "", placeholder="Enter student's full name")
                    student_id = st.text_input("Student ID Number *", value=st.session_state.user['username'] if role == 'Student' else "", placeholder="e.g., H240309Y", disabled=(role == 'Student'))
                with col2:
                    contact_number = st.text_input("Contact Number *", placeholder="e.g., 0771234567")
                
                st.subheader("💻 Device Information")
                col1, col2, col3 = st.columns(3)
                with col1:
                    laptop_brand = st.text_input("Laptop Brand *", placeholder="e.g., HP, Dell, Lenovo")
                    laptop_serial = st.text_input("Serial Number *", placeholder="Unique serial number")
                with col2:
                    laptop_model = st.text_input("Model *", placeholder="e.g., EliteBook 840 G7")
                    color = st.text_input("Color", placeholder="e.g., Silver, Black")
                
                st.markdown("**Required fields*")
                submitted = st.form_submit_button("🚀 Register Device & Generate QR Code")
                
                if submitted:
                    if not all([student_name, student_id, laptop_serial, laptop_brand, laptop_model, contact_number]):
                        st.markdown('<div class="error-box">❌ Please fill in all required fields (marked with *)</div>', unsafe_allow_html=True)
                    else:
                        student_data = {
                            'student_name': student_name,
                            'student_id': student_id.upper(),
                            'laptop_serial': laptop_serial.upper(),
                            'laptop_brand': laptop_brand,
                            'laptop_model': laptop_model,
                            'color': color,
                            'contact_number': contact_number,
                            'registration_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        success, result, qr_img_bytes = asset_manager.register_laptop(student_data)
                        
                        if success:
                            # If registered by a student for themselves, they might need to logout and back in to see updated info if they used guest login
                            # In this system, we'll just store it in session state
                            st.session_state.registration_data = student_data
                            st.session_state.qr_code_bytes = qr_img_bytes
                            st.rerun()
                        elif success == "CONFISCATED":
                            st.error(result)
                            st.markdown(f'<div class="error-box">🚨 {result}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="error-box">❌ Registration failed: {result}</div>', unsafe_allow_html=True)
    
    # Verify Ownership
    elif choice == "🔍 Verify Ownership":
        st.markdown('<div class="sub-header">Device Verification</div>', unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["📱 QR Code Verification", "🔢 Manual Verification"])
        
        with tab1:
            st.subheader("QR Code Scanner")
            
            col1, col2 = st.columns(2)
            with col1:
                location = st.selectbox("Verification Location", 
                                      ["Main Gate", "Library", "Hostel", "Lecture Hall", "Other"])
                verified_by = st.text_input("Verified By", value=st.session_state.user['full_name'], placeholder="Your name")
            
            st.markdown('<div class="info-box">📸 **Instructions:** Use a QR scanner app on your phone or upload a QR code image below.</div>', unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader("Upload QR Code Image", type=['png', 'jpg', 'jpeg'])
            
            if uploaded_file is not None:
                # Display uploaded image
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded QR Code", width=300)
                
                st.markdown('<div class="info-box">🔧 **Note:** In production, this would automatically decode QR codes using libraries like pyzbar</div>', unsafe_allow_html=True)
                
                # Manual QR data input for demo
                st.subheader("Or Enter QR Code Data Manually")
                qr_data = st.text_area("QR Code Data", placeholder='Paste QR code data here (JSON format)...', height=100)
                
                if st.button("🔍 Verify QR Code", use_container_width=True):
                    if qr_data.strip():
                        success, result = asset_manager.verify_laptop(qr_data, location, verified_by)
                        
                        if success:
                            if success == "STOLEN":
                                st.error("🚨 STOLEN DEVICE DETECTED! 🚨")
                                st.markdown('<div class="error-box">', unsafe_allow_html=True)
                                st.subheader("⚠️ SECURITY ALERT")
                                st.write("This device has been reported as **STOLEN** or **LOST**.")
                                if isinstance(result, (pd.Series, dict)):
                                    st.write(f"**Owner:** {result['student_name']} ({result['student_id']})")
                                    st.write(f"**Serial:** {result['laptop_serial']}")
                                st.write("Please detain the individual and contact campus security immediately.")
                                st.markdown('</div>', unsafe_allow_html=True)
                            else:
                                st.balloons()
                                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                                st.success("✅ OWNERSHIP VERIFIED SUCCESSFULLY!")
                                
                                st.subheader("📋 Device Information")
                                if isinstance(result, (pd.Series, dict)):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**Student Name:** {result['student_name']}")
                                        st.write(f"**Student ID:** {result['student_id']}")
                                        st.write(f"**Contact:** {result['contact_number']}")
                                    with col2:
                                        st.write(f"**Device:** {result['laptop_brand']} {result['laptop_model']}")
                                        st.write(f"**Serial:** {result['laptop_serial']}")
                                        st.write(f"**Color:** {result['color']}")
                                        st.write(f"**Registered:** {result['registration_date']}")
                                    
                                    st.markdown('</div>', unsafe_allow_html=True)
                                    
                                    # Show QR code from saved file path
                                    if 'qr_code_path' in result and os.path.exists(result['qr_code_path']):
                                        st.image(result['qr_code_path'], caption="Registered QR Code", width=200)
                            
                        else:
                            st.markdown('<div class="error-box">', unsafe_allow_html=True)
                            st.error("❌ VERIFICATION FAILED")
                            st.write(f"**Reason:** {result}")
                            st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="error-box">❌ Please enter QR code data</div>', unsafe_allow_html=True)
        
        with tab2:
            st.subheader("Manual Verification")
            st.markdown('<div class="info-box">🔍 Use this when QR code is unavailable or damaged</div>', unsafe_allow_html=True)
            
            with st.form("manual_verification"):
                col1, col2 = st.columns(2)
                with col1:
                    manual_student_id = st.text_input("Student ID", placeholder="e.g., H240309Y")
                    manual_location = st.selectbox("Location", 
                                                ["Main Gate", "Library", "Hostel", "Lecture Hall", "Other"], key="manual_loc")
                with col2:
                    manual_laptop_serial = st.text_input("Laptop Serial", placeholder="Enter Serial Number")
                    manual_verified_by = st.text_input("Verified By", value=st.session_state.user['full_name'], key="manual_verifier")
                
                if st.form_submit_button("🔍 Verify Manually", use_container_width=True):
                    if manual_student_id and manual_laptop_serial:
                        # Search for device
                        df = asset_manager.get_all_laptops()
                        laptop = df[
                            (df['student_id'] == manual_student_id.upper()) & 
                            (df['laptop_serial'] == manual_laptop_serial.upper())
                        ]
                        
                        if not laptop.empty:
                            laptop_data = laptop.iloc[0]
                            
                            # Check for lost/stolen status
                            if laptop_data.get('status') == 'Lost/Stolen':
                                st.error("🚨 STOLEN DEVICE DETECTED! 🚨")
                                st.markdown('<div class="error-box">', unsafe_allow_html=True)
                                st.subheader("⚠️ SECURITY ALERT")
                                st.write("This device has been reported as **STOLEN** or **LOST**.")
                                if isinstance(laptop_data, (pd.Series, dict)):
                                    st.write(f"**Owner:** {laptop_data['student_name']} ({laptop_data['student_id']})")
                                    st.write(f"**Serial:** {laptop_data['laptop_serial']}")
                                st.write("Please detain the individual and contact campus security immediately.")
                                st.markdown('</div>', unsafe_allow_html=True)
                                
                                # Log detection
                                asset_manager.log_verification(
                                    datetime.now().isoformat(),
                                    manual_student_id.upper(),
                                    laptop_data['student_name'] if isinstance(laptop_data, (pd.Series, dict)) else "Unknown",
                                    manual_laptop_serial.upper(),
                                    "Manual Check",
                                    manual_location,
                                    manual_verified_by,
                                    "STOLEN DEVICE DETECTED"
                                )
                            else:
                                st.balloons()
                                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                                st.success("✅ OWNERSHIP VERIFIED SUCCESSFULLY!")
                                
                                if isinstance(laptop_data, (pd.Series, dict)):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**Student Name:** {laptop_data['student_name']}")
                                        st.write(f"**Student ID:** {laptop_data['student_id']}")
                                        st.write(f"**Contact:** {laptop_data['contact_number']}")
                                    with col2:
                                        st.write(f"**Device:** {laptop_data['laptop_brand']} {laptop_data['laptop_model']}")
                                        st.write(f"**Serial:** {laptop_data['laptop_serial']}")
                                        st.write(f"**Color:** {laptop_data['color']}")
                                
                                st.markdown('</div>', unsafe_allow_html=True)
                                
                                # Log the verification
                                asset_manager.log_verification(
                                    datetime.now().isoformat(),
                                    manual_student_id.upper(),
                                    laptop_data['student_name'] if isinstance(laptop_data, (pd.Series, dict)) else "Unknown",
                                    manual_laptop_serial.upper(),
                                    "Manual Check",
                                    manual_location,
                                    manual_verified_by,
                                    "SUCCESS"
                                )
                            
                        else:
                            st.markdown('<div class="error-box">', unsafe_allow_html=True)
                            st.error("❌ VERIFICATION FAILED")
                            st.write("No matching device found in the system.")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Log failed attempt
                            asset_manager.log_verification(
                                datetime.now().isoformat(),
                                manual_student_id.upper(),
                                "Unknown",
                                manual_laptop_serial.upper(),
                                "Manual Check",
                                manual_location,
                                manual_verified_by,
                                "FAILED - Not Found"
                            )
                    else:
                        st.markdown('<div class="error-box">❌ Please enter both Student ID and Laptop Serial</div>', unsafe_allow_html=True)
    
    # View All Devices
    elif choice == "📊 View All Devices":
        st.markdown('<div class="sub-header">Registered Devices Database</div>', unsafe_allow_html=True)
        
        df = asset_manager.get_all_laptops()
        
        if df.empty:
            st.markdown('<div class="info-box">📭 No devices registered yet.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="success-box">📊 Found {len(df)} registered devices</div>', unsafe_allow_html=True)
            
            # Search and filter
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input("🔍 Search devices", placeholder="Search by name, ID, serial, brand...")
            with col2:
                st.write("")  # Spacer
                if st.button("🔄 Refresh Data", use_container_width=True):
                    st.rerun()
            
            # Filter data
            if search_term:
                filtered_df = asset_manager.search_laptops(search_term)
                st.markdown(f'<div class="info-box">🔍 Found {len(filtered_df)} devices matching "{search_term}"</div>', unsafe_allow_html=True)
            else:
                filtered_df = df
            
            # Display data
            if not filtered_df.empty:
                # Show as table
                st.dataframe(
                    filtered_df[['student_name', 'student_id', 'laptop_brand', 'laptop_model', 'laptop_serial', 'status', 'registration_date']],
                    use_container_width=True,
                    height=400
                )
                
                # Export options
                st.markdown("---")
                st.subheader("Export Data")
                
                col1, col2 = st.columns(2)
                with col1:
                    # CSV Export
                    csv_data = filtered_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Export as CSV",
                        data=csv_data,
                        file_name=f"HIT_devices_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col2:
                    # Excel Export with error handling
                    excel_data = convert_to_excel(filtered_df)
                    if excel_data is not None:
                        st.download_button(
                            label="📊 Export as Excel",
                            data=excel_data,
                            file_name=f"HIT_devices_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.ms-excel",
                            use_container_width=True
                        )
                    else:
                        st.info("📝 Excel export requires 'xlsxwriter' module. Please install it using: `pip install xlsxwriter`")
    
    # Verification Logs
    elif choice == "📋 Verification Logs":
        st.markdown('<div class="sub-header">Verification History & Audit Logs</div>', unsafe_allow_html=True)
        
        logs_df = asset_manager.get_verification_logs()
        
        if logs_df.empty:
            st.markdown('<div class="info-box">📭 No verification logs available yet.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="success-box">📋 Found {len(logs_df)} verification records</div>', unsafe_allow_html=True)
            
            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox("Filter by Status", ["All", "SUCCESS", "FAILED"])
            with col2:
                location_filter = st.selectbox("Filter by Location", ["All"] + list(logs_df['location'].unique()))
            with col3:
                date_filter = st.date_input("Filter by Date")
            
            # Apply filters
            filtered_logs = logs_df.copy()
            if status_filter != "All":
                if status_filter == "SUCCESS":
                    filtered_logs = filtered_logs[filtered_logs['status'] == 'SUCCESS']
                else:
                    filtered_logs = filtered_logs[filtered_logs['status'].str.startswith('FAILED')]
            
            if location_filter != "All":
                filtered_logs = filtered_logs[filtered_logs['location'] == location_filter]
            
            if date_filter:
                # Convert to datetime for filtering
                filtered_logs_temp = filtered_logs.copy()
                filtered_logs_temp['timestamp'] = pd.to_datetime(filtered_logs_temp['timestamp'])
                filtered_logs = filtered_logs_temp[filtered_logs_temp['timestamp'].dt.date == date_filter]
            
            st.markdown(f'<div class="info-box">🔍 Showing {len(filtered_logs)} filtered records</div>', unsafe_allow_html=True)
            
            # Display logs
            for _, log in filtered_logs.iterrows():
                with st.expander(f"{log['timestamp']} - {log['student_name']} - {log['status']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Student:** {log['student_name']} ({log['student_id']})")
                        st.write(f"**Device:** {log['laptop_serial']}")
                    with col2:
                        st.write(f"**Location:** {log['location']}")
                        st.write(f"**Verified by:** {log['verified_by']}")
                        st.write(f"**Type:** {log['verification_type']}")
                    
                    status_color = "🟢" if log['status'] == 'SUCCESS' else "🔴"
                    st.write(f"**Status:** {status_color} {log['status']}")
            
            # Export Option
            st.markdown("---")
            st.subheader("Export Reports for Printing")
            csv_logs = filtered_logs.to_csv(index=False)
            st.download_button(
                label="📥 Download Verification Logs (CSV)",
                data=csv_logs,
                file_name=f"Verification_Reports_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    # System Action Logs
    elif choice == "📜 System Action Logs":
        st.markdown('<div class="sub-header">System Activity & Audit Trail</div>', unsafe_allow_html=True)
        
        action_logs = asset_manager.get_action_logs()
        
        if action_logs.empty:
            st.markdown('<div class="info-box">📭 No action logs available yet.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="success-box">📋 Found {len(action_logs)} system activity records</div>', unsafe_allow_html=True)
            
            # Filters
            col1, col2 = st.columns(2)
            with col1:
                user_filter = st.selectbox("Filter by User", ["All"] + list(action_logs['user'].unique()))
            with col2:
                action_filter = st.selectbox("Filter by Action", ["All"] + list(action_logs['action'].unique()))
            
            filtered_actions = action_logs.copy()
            if user_filter != "All":
                filtered_actions = filtered_actions[filtered_actions['user'] == user_filter]
            if action_filter != "All":
                filtered_actions = filtered_actions[filtered_actions['action'] == action_filter]
            
            st.dataframe(filtered_actions, use_container_width=True)
            
            # Export Option
            st.markdown("---")
            st.subheader("Export Audit Trail")
            csv_actions = filtered_actions.to_csv(index=False)
            st.download_button(
                label="📥 Download Action Logs (CSV)",
                data=csv_actions,
                file_name=f"Action_Audit_Trail_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    # User Management (Admin Only)
    elif choice == "👤 User Management" and st.session_state.user['role'] == 'Admin':
        st.markdown('<div class="sub-header">System User Management</div>', unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["➕ Add New User", "👥 System Users"])
        
        with tab1:
            st.subheader("Register New System User")
            st.markdown('<div class="info-box">👤 Use this form to add new security guards or administrators.</div>', unsafe_allow_html=True)
            
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("Username *")
                    new_password = st.text_input("Password *", type="password")
                with col2:
                    new_full_name = st.text_input("Full Name *")
                    new_role = st.selectbox("Role", ["Security", "Admin"])
                
                if st.form_submit_button("👤 Register User", use_container_width=True):
                    if new_username and new_password and new_full_name:
                        user_data = {
                            'username': new_username,
                            'password': new_password,
                            'full_name': new_full_name,
                            'role': new_role
                        }
                        success, message = asset_manager.register_user(user_data)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.warning("⚠️ Please fill in all required fields.")
        
        with tab2:
            st.subheader("Manage Existing Users")
            users_df = asset_manager.get_all_users()
            if not users_df.empty:
                st.dataframe(users_df[['username', 'full_name', 'role']], use_container_width=True)
            else:
                st.info("No users found.")

    # Manage Device Status
    elif choice == "🔄 Manage Device Status":
        st.markdown('<div class="sub-header">Device Status Management</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">🔄 Use this section to update the status of a registered device (e.g., from Lost to Active).</div>', unsafe_allow_html=True)
        
        search_serial = st.text_input("🔍 Search by Laptop Serial Number", placeholder="Enter full serial number")
        
        if search_serial:
            df = asset_manager.get_all_laptops()
            device = df[df['laptop_serial'] == search_serial.upper()]
            
            if not device.empty:
                device_data = device.iloc[0]
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.subheader("📋 Device Information")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Owner:** {device_data['student_name']} ({device_data['student_id']})")
                    st.write(f"**Device:** {device_data['laptop_brand']} {device_data['laptop_model']}")
                with col2:
                    st.write(f"**Current Status:** {device_data['status']}")
                    st.write(f"**Serial:** {device_data['laptop_serial']}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown("### Update Status")
                with st.form("update_status_form"):
                    new_status = st.selectbox("Select New Status", ["Active", "Lost/Stolen", "Confiscated"], 
                                           index=["Active", "Lost/Stolen", "Confiscated"].index(device_data['status']) if device_data['status'] in ["Active", "Lost/Stolen", "Confiscated"] else 0)
                    reason = st.text_input("Reason for change", placeholder="e.g., Device found and returned")
                    
                    if st.form_submit_button("✅ Update Device Status", use_container_width=True):
                        if new_status == device_data['status']:
                            st.info("Status is already set to " + new_status)
                        else:
                            success, message = asset_manager.update_laptop_status(device_data['student_id'], search_serial.upper(), new_status)
                            if success:
                                # Log additional details
                                if reason:
                                    asset_manager.log_action(st.session_state.user['username'], "Status Update Info", search_serial.upper(), reason)
                                st.success(f"✅ {message}")
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
            else:
                st.error("❌ Device not found with that serial number.")

    # Report Lost Device
    elif choice == "🚨 Report Lost Device":
        st.markdown('<div class="sub-header">Lost Device Reporting</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="error-box">🚨 **Use this section to report lost or stolen devices immediately!**</div>', unsafe_allow_html=True)
        
        with st.form("lost_device_form"):
            col1, col2 = st.columns(2)
            with col1:
                lost_student_id = st.text_input("Student ID *", value=st.session_state.user['username'] if role == 'Student' else "", placeholder="e.g., H240309Y", disabled=(role == 'Student'))
                lost_contact = st.text_input("Contact Number *", placeholder="Where to reach you")
            with col2:
                default_serial = st.session_state.get('report_serial', "")
                lost_laptop_serial = st.text_input("Laptop Serial *", value=default_serial, placeholder="Serial number of lost device")
                lost_location = st.text_input("Where was it lost?", placeholder="e.g., Library, Hostel Room 101")
            
            lost_date = st.date_input("Date Lost", value=datetime.now().date())
            lost_description = st.text_area("Additional Details", placeholder="Describe the circumstances, distinctive features, etc.")
            
            if st.form_submit_button("🚨 Report as Lost", use_container_width=True):
                if lost_student_id and lost_laptop_serial and lost_contact:
                    # Verify device exists
                    df = asset_manager.get_all_laptops()
                    device = df[
                        (df['student_id'] == lost_student_id.upper()) & 
                        (df['laptop_serial'] == lost_laptop_serial.upper())
                    ]
                    
                    if not device.empty:
                        device_data = device.iloc[0]
                        
                        # Update status to Lost/Stolen
                        asset_manager.update_laptop_status(lost_student_id.upper(), lost_laptop_serial.upper(), "Lost/Stolen")
                        
                        # Log the report
                        asset_manager.log_verification(
                            datetime.now().isoformat(),
                            lost_student_id.upper(),
                            device_data['student_name'],
                            lost_laptop_serial.upper(),
                            "Lost Device Report",
                            lost_location,
                            "System",
                            f"LOST - {lost_description}"
                        )
                        
                        st.markdown('<div class="error-box">', unsafe_allow_html=True)
                        st.error("🚨 LOST DEVICE REPORTED!")
                        st.write("**Immediate Actions Taken:**")
                        st.write("1. ✅ Lost report logged in system")
                        st.write("2. ✅ Security department notified")
                        st.write("3. ✅ Device flagged for recovery")
                        st.write("4. ✅ Contact information recorded")
                        
                        st.write("\n**Device Information:**")
                        st.write(f"- **Owner:** {device_data['student_name']}")
                        st.write(f"- **Device:** {device_data['laptop_brand']} {device_data['laptop_model']}")
                        st.write(f"- **Serial:** {device_data['laptop_serial']}")
                        st.write(f"- **Color:** {device_data['color']}")
                        
                        st.write("\n**Next Steps:**")
                        st.write("- Contact campus security immediately")
                        st.write("- Provide any additional information")
                        st.write("- Check lost and found regularly")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="error-box">❌ Device not found. Please check Student ID and Serial Number.</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="error-box">❌ Please fill in all required fields.</div>', unsafe_allow_html=True)

    # My Devices (Student Only)
    elif choice == "💻 My Devices":
        st.markdown('<div class="sub-header">My Registered Devices</div>', unsafe_allow_html=True)
        
        student_id = st.session_state.user['username']
        df = asset_manager.get_all_laptops()
        my_devices = df[df['student_id'] == student_id] if not df.empty else pd.DataFrame()
        
        if my_devices.empty:
            st.markdown('<div class="info-box">📭 You haven\'t registered any devices yet.</div>', unsafe_allow_html=True)
            if st.button("📝 Register Your First Device"):
                st.session_state.choice = "📝 Register New Device"
                st.rerun()
        else:
            for _, device in my_devices.iterrows():
                with st.expander(f"📦 {device['laptop_brand']} {device['laptop_model']} ({device['laptop_serial']}) - {device['status']}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Serial:** {device['laptop_serial']}")
                        st.write(f"**Color:** {device['color']}")
                        st.write(f"**Status:** {device['status']}")
                        st.write(f"**Registered on:** {device['registration_date']}")
                    
                    with col2:
                        if os.path.exists(device['qr_code_path']):
                            st.image(device['qr_code_path'], width=150)
                            with open(device['qr_code_path'], "rb") as file:
                                st.download_button(
                                    label="📥 Download QR Code",
                                    data=file,
                                    file_name=f"QR_{device['laptop_serial']}.png",
                                    mime="image/png",
                                    use_container_width=True
                                )
                    
                    if device['status'] == 'Active':
                        if st.button(f"🚨 Report {device['laptop_serial']} as Lost", key=f"lost_{device['laptop_serial']}"):
                            st.session_state.choice = "🚨 Report Lost Device"
                            st.session_state.report_serial = device['laptop_serial']
                            st.rerun()

    # Notifications (Student Only)
    elif choice == "🔔 Notifications":
        st.markdown('<div class="sub-header">My Notifications</div>', unsafe_allow_html=True)
        
        student_id = st.session_state.user['username']
        notifs = asset_manager.get_notifications(student_id)
        
        if notifs.empty:
            st.markdown('<div class="info-box">📭 No notifications available.</div>', unsafe_allow_html=True)
        else:
            if st.button("✅ Mark All as Read"):
                asset_manager.mark_notifications_read(student_id)
                st.rerun()
                
            for _, notif in notifs.iterrows():
                style = "background: rgba(34, 211, 238, 0.1); border-left: 4px solid #22d3ee;" if notif['status'] == 'Unread' else "background: white; border-left: 4px solid #94a3b8;"
                st.markdown(f'''
                <div style="padding: 1.5rem; margin-bottom: 1rem; border-radius: 0.75rem; {style} box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <span style="font-weight: 700; color: #1e293b;">{notif['timestamp']}</span>
                        <span style="background: {'#22d3ee' if notif['status'] == 'Unread' else '#e2e8f0'}; color: {'#083344' if notif['status'] == 'Unread' else '#475569'}; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 700;">{notif['status']}</span>
                    </div>
                    <div style="margin-top: 1rem; color: #334155; line-height: 1.5;">{notif['message']}</div>
                </div>
                ''', unsafe_allow_html=True)

    # System Settings
    elif choice == "⚙️ System Settings":
        st.markdown('<div class="sub-header">System Administration</div>', unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["📊 Database Management", "ℹ️ System Info", "💾 Backup/Restore"])
        
        with tab1:
            st.subheader("Database Management")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Registered Devices", len(asset_manager.get_all_laptops()))
                st.metric("Verification Logs", len(asset_manager.get_verification_logs()))
                st.metric("QR Codes Generated", len([f for f in os.listdir("qr_codes") if f.endswith('.png')]))
            
            with col2:
                if st.button("🔄 Update Statistics", use_container_width=True):
                    st.rerun()
                
                if st.button("🧹 Clear All Data", type="secondary", use_container_width=True):
                    st.markdown('<div class="error-box">🚨 This will delete ALL data! Proceed with caution.</div>', unsafe_allow_html=True)
                    if st.button("⚠️ CONFIRM DELETE ALL DATA", type="primary"):
                        try:
                            if os.path.exists(asset_manager.laptops_file):
                                os.remove(asset_manager.laptops_file)
                            if os.path.exists(asset_manager.logs_file):
                                os.remove(asset_manager.logs_file)
                            # Reinitialize
                            asset_manager.initialize_files()
                            st.markdown('<div class="success-box">✅ All data cleared successfully!</div>', unsafe_allow_html=True)
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.markdown(f'<div class="error-box">❌ Error clearing data: {e}</div>', unsafe_allow_html=True)
        
        with tab2:
            st.subheader("System Information")
            st.markdown('<div class="info-box">', unsafe_allow_html=True)
            st.write(f"**System Version:** HIT Asset Verification System v2.0")
            st.write(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            st.write(f"**Data Storage:** CSV Files")
            st.write(f"**QR Code Storage:** {len([f for f in os.listdir('qr_codes') if f.endswith('.png')])} files")
            st.write(f"**Data Directory:** ./data/")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.subheader("System Health")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown('<div class="success-box">✅ Database: OK</div>', unsafe_allow_html=True)
            with col2:
                st.markdown('<div class="success-box">✅ QR System: OK</div>', unsafe_allow_html=True)
            with col3:
                st.markdown('<div class="success-box">✅ Logging: OK</div>', unsafe_allow_html=True)
        
        with tab3:
            st.subheader("Backup & Restore")
            st.markdown('<div class="info-box">💾 Backup your data regularly to prevent loss.</div>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                # Backup
                if st.button("📦 Create Backup", use_container_width=True):
                    backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_dir = f"backup_{backup_time}"
                    os.makedirs(backup_dir, exist_ok=True)
                    
                    # Copy files
                    import shutil
                    shutil.copy2(asset_manager.laptops_file, backup_dir)
                    shutil.copy2(asset_manager.logs_file, backup_dir)
                    shutil.copytree("qr_codes", os.path.join(backup_dir, "qr_codes"))
                    
                    # Create zip
                    shutil.make_archive(backup_dir, 'zip', backup_dir)
                    shutil.rmtree(backup_dir)
                    
                    st.markdown(f'<div class="success-box">✅ Backup created: {backup_dir}.zip</div>', unsafe_allow_html=True)
            
            with col2:
                # Restore
                uploaded_backup = st.file_uploader("Upload Backup ZIP", type=['zip'])
                if uploaded_backup and st.button("🔄 Restore from Backup", use_container_width=True):
                    st.markdown('<div class="error-box">🚨 This will overwrite current data!</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
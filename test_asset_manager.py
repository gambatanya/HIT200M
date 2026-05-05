import pandas as pd
import os
import sys
from datetime import datetime

# Add the current directory to sys.path to import from it if needed
sys.path.append(os.getcwd())

# Mock streamlit for AssetManager if it uses it globally
# In our app.py, AssetManager doesn't seem to use st in __init__, 
# but it uses it in log_action.
import unittest.mock as mock
sys.modules['streamlit'] = mock.Mock()

from app import AssetManager

def test_user_management():
    print("Testing User Management...")
    am = AssetManager()
    
    # Test Add User
    test_user = {
        'username': 'testuser123',
        'password': 'password123',
        'full_name': 'Test User',
        'role': 'Security'
    }
    success, msg = am.register_user(test_user)
    print(f"Register User: {success} - {msg}")
    
    # Test Update Role
    success, msg = am.update_user_role('testuser123', 'Admin')
    print(f"Update Role: {success} - {msg}")
    
    users = am.get_all_users()
    updated_user = users[users['username'] == 'testuser123'].iloc[0]
    assert updated_user['role'] == 'Admin', "Role update failed"
    
    # Test Delete User
    success, msg = am.delete_user('testuser123')
    print(f"Delete User: {success} - {msg}")
    
    users = am.get_all_users()
    assert 'testuser123' not in users['username'].values, "User deletion failed"
    print("User Management tests passed!")

def test_sighting_updates():
    print("\nTesting Sighting Updates...")
    am = AssetManager()
    
    # Check if we have any laptops to test with
    laptops = am.get_all_laptops()
    if laptops.empty:
        print("No laptops found for sightings test.")
        return
        
    target = laptops.iloc[0]
    original_loc = target['last_seen_location']
    
    success = am.update_device_sighting(target['student_id'], target['laptop_serial'], "Test Gate")
    print(f"Update Sighting: {success}")
    
    updated_laptops = am.get_all_laptops()
    updated_target = updated_laptops[updated_laptops['laptop_serial'] == target['laptop_serial']].iloc[0]
    assert updated_target['last_seen_location'] == "Test Gate", "Sighting update failed"
    print("Sighting tests passed!")

if __name__ == "__main__":
    try:
        test_user_management()
        test_sighting_updates()
        print("\nAll integration tests PASSED!")
    except Exception as e:
        print(f"\nTests FAILED: {e}")

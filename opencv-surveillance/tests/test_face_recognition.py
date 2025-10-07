# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Comprehensive testing script for OpenEye Face Recognition
Tests all major components of the face recognition system
"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
TEST_PERSON_NAME = "Test Person"


class FaceRecognitionTester:
    """Test suite for face recognition functionality"""
    
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.token = None
        self.test_results = []
    
    def log_test(self, test_name, success, message=""):
        """Log test result"""
        status = "✓ PASS" if success else "✗ FAIL"
        result = f"{status} - {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def test_health_check(self):
        """Test 1: Health check endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/health")
            success = response.status_code == 200
            self.log_test("Health Check", success, f"Status: {response.json().get('status')}")
            return success
        except Exception as e:
            self.log_test("Health Check", False, str(e))
            return False
    
    def test_list_people(self):
        """Test 2: List people endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/faces/people")
            success = response.status_code == 200
            people = response.json()
            self.log_test("List People", success, f"Found {len(people)} people")
            return success
        except Exception as e:
            self.log_test("List People", False, str(e))
            return False
    
    def test_add_person(self):
        """Test 3: Add new person"""
        try:
            response = requests.post(
                f"{self.base_url}/api/faces/people",
                json={"name": TEST_PERSON_NAME}
            )
            success = response.status_code in [200, 201]
            self.log_test("Add Person", success, f"Added '{TEST_PERSON_NAME}'")
            return success
        except Exception as e:
            self.log_test("Add Person", False, str(e))
            return False
    
    def test_get_statistics(self):
        """Test 4: Get face recognition statistics"""
        try:
            response = requests.get(f"{self.base_url}/api/faces/statistics")
            success = response.status_code == 200
            stats = response.json()
            self.log_test(
                "Get Statistics",
                success,
                f"People: {stats.get('total_people')}, Encodings: {stats.get('total_encodings')}"
            )
            return success
        except Exception as e:
            self.log_test("Get Statistics", False, str(e))
            return False
    
    def test_get_settings(self):
        """Test 5: Get face recognition settings"""
        try:
            response = requests.get(f"{self.base_url}/api/faces/settings")
            success = response.status_code == 200
            settings = response.json()
            self.log_test(
                "Get Settings",
                success,
                f"Method: {settings.get('detection_method')}, Threshold: {settings.get('recognition_threshold')}"
            )
            return success
        except Exception as e:
            self.log_test("Get Settings", False, str(e))
            return False
    
    def test_update_settings(self):
        """Test 6: Update face recognition settings"""
        try:
            new_settings = {
                "enabled": True,
                "detection_method": "hog",
                "recognition_threshold": 0.6,
                "faces_folder": "faces"
            }
            response = requests.put(
                f"{self.base_url}/api/faces/settings",
                json=new_settings
            )
            success = response.status_code == 200
            self.log_test("Update Settings", success, "Settings updated")
            return success
        except Exception as e:
            self.log_test("Update Settings", False, str(e))
            return False
    
    def test_camera_face_detection(self):
        """Test 7: Enable face detection on camera"""
        try:
            response = requests.post(
                f"{self.base_url}/api/faces/camera/mock_cam_1/enable?enabled=true"
            )
            success = response.status_code == 200
            self.log_test("Camera Face Detection", success, "Enabled for mock_cam_1")
            return success
        except Exception as e:
            self.log_test("Camera Face Detection", False, str(e))
            return False
    
    def test_get_detections(self):
        """Test 8: Get recent face detections"""
        try:
            response = requests.get(f"{self.base_url}/api/faces/detections")
            success = response.status_code == 200
            detections = response.json()
            self.log_test("Get Detections", success, f"Found detections from {len(detections)} cameras")
            return success
        except Exception as e:
            self.log_test("Get Detections", False, str(e))
            return False
    
    def test_system_info(self):
        """Test 9: Get system information"""
        try:
            response = requests.get(f"{self.base_url}/api/system/info")
            success = response.status_code == 200
            info = response.json()
            self.log_test(
                "System Info",
                success,
                f"Total cameras: {info.get('total_cameras')}"
            )
            return success
        except Exception as e:
            self.log_test("System Info", False, str(e))
            return False
    
    def test_delete_person(self):
        """Test 10: Delete test person"""
        try:
            response = requests.delete(
                f"{self.base_url}/api/faces/people/{TEST_PERSON_NAME}"
            )
            success = response.status_code in [200, 404]  # 404 is ok if already deleted
            self.log_test("Delete Person", success, f"Deleted '{TEST_PERSON_NAME}'")
            return success
        except Exception as e:
            self.log_test("Delete Person", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*60)
        print("OpenEye Face Recognition Test Suite")
        print("="*60 + "\n")
        
        print("Waiting for server to be ready...")
        time.sleep(2)
        
        tests = [
            self.test_health_check,
            self.test_list_people,
            self.test_add_person,
            self.test_get_statistics,
            self.test_get_settings,
            self.test_update_settings,
            self.test_camera_face_detection,
            self.test_get_detections,
            self.test_system_info,
            self.test_delete_person
        ]
        
        for test in tests:
            test()
            time.sleep(0.5)  # Small delay between tests
        
        # Print summary
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        
        passed = sum(1 for r in self.test_results if r['success'])
        total = len(self.test_results)
        
        print(f"\nTests Passed: {passed}/{total}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n🎉 All tests passed! Face recognition system is working correctly.")
        else:
            print("\n⚠️  Some tests failed. Please check the errors above.")
        
        print("\n" + "="*60 + "\n")
        
        return passed == total


def main():
    """Run the test suite"""
    tester = FaceRecognitionTester()
    
    try:
        all_passed = tester.run_all_tests()
        exit(0 if all_passed else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\nFatal error running tests: {e}")
        exit(1)


if __name__ == "__main__":
    main()
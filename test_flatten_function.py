import os
import sys
import django

# Add the server path so we can import Django modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.exceptions import ValidationError
from apps.core.importers import flatten_validation_errors

# Test the function with different types of ValidationError
def test_flatten_function():
    print("Testing flatten_validation_errors function...")
    
    # Test with dict-style errors
    try:
        error_dict = ValidationError({'field1': ['error1', 'error2'], 'field2': ['error3']})
        result = flatten_validation_errors(error_dict)
        print(f"Dict-style error result: {result}")
        print(f"Result type: {type(result)}")
    except Exception as e:
        print(f"Error with dict-style test: {e}")
        
    # Test with list-style errors
    try:
        error_list = ValidationError(['general error 1', 'general error 2'])
        result = flatten_validation_errors(error_list)
        print(f"List-style error result: {result}")
        print(f"Result type: {type(result)}")
    except Exception as e:
        print(f"Error with list-style test: {e}")

if __name__ == "__main__":
    test_flatten_function()

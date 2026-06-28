# import_students.py
import os
import sys
import csv
import datetime
from decimal import Decimal

# 1. Setup Django Environment
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mylon.settings") # Adjust to your actual settings path if different
django.setup()

from django.db import transaction
from students.models import Campus, Grade, Student, Term, GradeTermFee, Invoice

def run_bulk_import():
    csv_file_path = "students_migration.csv"
    
    if not os.path.exists(csv_file_path):
        print(f"❌ Error: Could not locate '{csv_file_path}' in the root directory.")
        return

    print("🚀 Starting secure student data pipeline migration...")
    
    # Pre-fetch active invoice term targets to speed up processing
    current_term = Term.objects.filter(is_current=True).first()
    if not current_term:
        print("⚠️ Warning: No globally active 'current' Term set in system. Initial invoices will not be generated automatically.")

    success_count = 0
    error_count = 0

    with open(csv_file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        # Open an atomic transaction framework block
        try:
            with transaction.atomic():
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        # Fetch or flag relational database targets
                        campus_obj = Campus.objects.filter(name__iexact=row['campus_name'].strip()).first()
                        if not campus_obj:
                            print(f"❌ Row {row_idx}: Campus '{row['campus_name']}' not found in DB. Skipping.")
                            error_count += 1
                            continue

                        grade_obj = Grade.objects.filter(title__iexact=row['grade_title'].strip()).first()
                        if not grade_obj:
                            print(f"❌ Row {row_idx}: Grade '{row['grade_title']}' not found in DB. Skipping.")
                            error_count += 1
                            continue

                        # Instantiate the profile object layout mapping strings dynamically
                        student = Student(
                            campus=campus_obj,
                            grade=grade_obj,
                            name=row['name'].strip(),
                            date_of_birth=datetime.datetime.strptime(row['date_of_birth'].strip(), "%Y-%m-%d").date(),
                            gender=row['gender'].strip().upper(),
                            parent_name=row['parent_name'].strip(),
                            phone_number_1=row['phone_number_1'].strip(),
                            neighborhood=row['neighborhood'].strip(),
                            city=row['city'].strip(),
                            country=row['country'].strip(),
                            status='ACTIVE'
                        )
                        
                        # Triggering your custom save() method allows it to automatically compute 
                        # the sequential Student ID and instantiate their initial invoice fees rule!
                        student.save()
                        success_count += 1
                        
                    except Exception as row_error:
                        print(f"❌ Error on Row {row_idx} ({row.get('name')}): {str(row_error)}")
                        error_count += 1
                        
            print(f"\n🎉 Data Pipeline Run Complete!")
            print(f"✅ Successfully Imported: {success_count} students.")
            print(f"❌ Skipped/Failed Rows: {error_count} records.")

        except Exception as tx_error:
            print(f"🚨 Transaction Failure: Migration aborted entirely. Reason: {str(tx_error)}")

if __name__ == "__main__":
    run_bulk_import()
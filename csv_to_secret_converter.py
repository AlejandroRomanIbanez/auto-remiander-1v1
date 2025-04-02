import csv

def convert_csv_to_env_string(csv_file):
    with open(csv_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        escaped = "\\n".join(lines)
        print("STUDENTS_DATA for Github Secret:" + escaped)


convert_csv_to_env_string("students.csv")

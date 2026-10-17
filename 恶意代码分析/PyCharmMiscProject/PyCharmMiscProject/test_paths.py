# test_paths.py
import os
import glob

BASE_DIR = r"C:\Users\26805\PyCharmMiscProject"
RULE_DIR = os.path.join(BASE_DIR, "rule")

print(f"BASE_DIR: {BASE_DIR}")
print(f"RULE_DIR: {RULE_DIR}")
print(f"当前工作目录: {os.getcwd()}")

# 检查关键文件
target_file = os.path.join(RULE_DIR, "antidebug_antivm", "antidebug_antivm.yar")
print(f"目标文件: {target_file}")
print(f"文件是否存在: {os.path.exists(target_file)}")

# 列出所有YARA文件
yara_files = glob.glob(os.path.join(RULE_DIR, "**", "*.yar"), recursive=True)
print(f"找到 {len(yara_files)} 个YARA文件")

# 检查前5个文件的include语句
for yara_file in yara_files[:5]:
    try:
        with open(yara_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if "include" in content:
                print(f"\n文件: {os.path.basename(yara_file)}")
                lines = content.split('\n')
                for i, line in enumerate(lines[:10]):  # 只看前10行
                    if "include" in line:
                        print(f"  行 {i+1}: {line.strip()}")
    except:
        pass
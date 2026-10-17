import os
import sys
import yaml
import yara
import glob

# 配置路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULE_DIR = os.path.join(BASE_DIR, 'rule')
SAMPLE_DIR = os.path.join(BASE_DIR, 'sample')

def load_yara_rules(rule_dir):
    """
    加载并编译指定目录下的所有YARA规则（递归查找）
    """
    rules = {}
    # 使用 recursive=True 递归查找子目录
    yara_files = glob.glob(os.path.join(rule_dir, '**', '*.yar'), recursive=True) + \
                 glob.glob(os.path.join(rule_dir, '**', '*.yara'), recursive=True)

    if not yara_files:
        print(f"[!] 在 {rule_dir} 及其子目录中未找到YARA规则文件 (.yar, .yara)")
        return None

    print(f"[*] 发现 {len(yara_files)} 个YARA规则文件")

    # 为了方便管理，我们将文件名作为命名空间
    # 改用 sources 方式加载，避免中文路径导致 yara C库 找不到文件的问题
    sources = {}
    for f in yara_files:
        # 使用文件名（无后缀）作为namespace，避免规则名称冲突
        # 清理 namespace，确保只包含字母数字下划线
        filename = os.path.splitext(os.path.basename(f))[0]
        namespace = "".join([c if c.isalnum() else "_" for c in filename])
        # namespace 不能以数字开头
        if namespace and namespace[0].isdigit():
            namespace = "_" + namespace

        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as rf:
                sources[namespace] = rf.read()
        except Exception as e:
            print(f"[-] 读取规则文件失败 {f}: {e}")

    if not sources:
        print("[-] 没有成功读取到任何YARA规则内容")
        return None

    try:
        compiled_rules = yara.compile(sources=sources)
        print("[+] YARA规则编译成功")
        return compiled_rules
    except yara.SyntaxError as e:
        print(f"[-] YARA规则编译失败: {e}")
        return None
    except Exception as e:
        print(f"[-] 加载YARA规则时发生错误: {e}")
        return None

class SimpleSigmaMatcher:
    """
    一个简化的Sigma规则匹配器。
    注意：完整的Sigma匹配需要解析复杂的逻辑（selection, condition, aggregation等）并映射到具体的日志字段。
    这里实现的是一个基于关键字的简化版本，用于演示目的，主要检查文件中是否包含规则中定义的特定字符串。
    """
    def __init__(self, rule_path):
        self.rule_path = rule_path
        self.rule_name = os.path.basename(rule_path)
        self.data = self._load_rule()
        self.keywords = self._extract_keywords()

    def _load_rule(self):
        try:
            with open(self.rule_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[-] 无法加载Sigma规则 {self.rule_path}: {e}")
            return None

    def _extract_keywords(self):
        """
        从detection字段提取用于匹配的关键字
        """
        keywords = []
        if not self.data or 'detection' not in self.data:
            return keywords

        detection = self.data['detection']
        for key, value in detection.items():
            if key == 'condition':
                continue
            
            # 递归查找字符串值
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, str):
                        keywords.append(v)
                    elif isinstance(v, list):
                        for item in v:
                            if isinstance(item, str):
                                keywords.append(item)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        keywords.append(item)
            elif isinstance(value, str):
                keywords.append(value)
        
        return list(set(keywords)) # 去重

    def match(self, file_content):
        """
        检查文件内容是否包含规则中的关键字
        """
        if not self.keywords:
            return False
        
        # 简单的逻辑：如果规则中提取出的任何关键字存在于文件中，则视为命中
        # 实际场景中应根据 'condition' 字段实现更复杂的逻辑
        
        # 这里我们假设如果是二进制文件，尝试解码或直接匹配字节
        try:
            text_content = file_content.decode('utf-8', errors='ignore')
        except:
            text_content = str(file_content)

        matches = []
        for kw in self.keywords:
            if kw in text_content:
                matches.append(kw)
        
        return matches

def load_sigma_rules(rule_dir):
    """
    加载指定目录下的所有Sigma规则（递归查找）
    """
    # 使用 recursive=True 递归查找子目录
    sigma_files = glob.glob(os.path.join(rule_dir, '**', '*.yml'), recursive=True) + \
                  glob.glob(os.path.join(rule_dir, '**', '*.yaml'), recursive=True)
    matchers = []
    
    if not sigma_files:
        print(f"[!] 在 {rule_dir} 及其子目录中未找到Sigma规则文件 (.yml, .yaml)")
        return []

    print(f"[*] 发现 {len(sigma_files)} 个Sigma规则文件")
    
    for f in sigma_files:
        matcher = SimpleSigmaMatcher(f)
        if matcher.data:
            matchers.append(matcher)
            
    return matchers

def analyze_samples(sample_dir, yara_rules, sigma_matchers):
    """
    遍历样本目录并进行分析
    """
    if not os.path.exists(sample_dir):
        print(f"[-] 样本目录不存在: {sample_dir}")
        return

    samples = [f for f in os.listdir(sample_dir) if os.path.isfile(os.path.join(sample_dir, f))]
    
    if not samples:
        print(f"[!] {sample_dir} 中没有文件")
        return

    print(f"\n[*] 开始分析 {len(samples)} 个样本...\n")
    print("="*60)

    for sample in samples:
        sample_path = os.path.join(sample_dir, sample)
        print(f"正在分析: {sample}")
        
        try:
            with open(sample_path, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            print(f"[-] 无法读取文件 {sample}: {e}")
            continue

        # 1. YARA 分析
        print("  [YARA 扫描]")
        if yara_rules:
            try:
                matches = yara_rules.match(data=file_content)
                if matches:
                    for match in matches:
                        print(f"    [+] 命中规则: {match.rule} (Namespace: {match.namespace})")
                        # 如果有元数据，也可以打印
                        # if match.meta:
                        #     print(f"        Meta: {match.meta}")
                else:
                    print("    [-] 未命中YARA规则")
            except Exception as e:
                print(f"    [-] YARA扫描出错: {e}")
        else:
            print("    [!] YARA规则未加载，跳过")

        # 2. Sigma 分析 (简化版)
        print("  [Sigma 扫描 (简化关键字匹配)]")
        if sigma_matchers:
            sigma_hits = False
            for matcher in sigma_matchers:
                hits = matcher.match(file_content)
                if hits:
                    sigma_hits = True
                    print(f"    [+] 可能命中 Sigma 规则: {matcher.data.get('title', matcher.rule_name)}")
                    print(f"        匹配关键字: {hits[:5]} ...") # 只显示前5个
            
            if not sigma_hits:
                print("    [-] 未命中 Sigma 关键字")
        else:
            print("    [!] Sigma规则未加载，跳过")

        print("-" * 60)

def main():
    print("=== 恶意代码自动化分析脚本 ===")
    print(f"规则目录: {RULE_DIR}")
    print(f"样本目录: {SAMPLE_DIR}")
    
    # 检查目录是否存在
    if not os.path.exists(RULE_DIR):
        os.makedirs(RULE_DIR)
        print(f"[+] 创建了规则目录: {RULE_DIR}")
    if not os.path.exists(SAMPLE_DIR):
        os.makedirs(SAMPLE_DIR)
        print(f"[+] 创建了样本目录: {SAMPLE_DIR}")

    # 加载规则
    print("\n[1/3] 加载规则...")
    yara_rules = load_yara_rules(RULE_DIR)
    sigma_matchers = load_sigma_rules(RULE_DIR)

    # 分析样本
    print("\n[2/3] 分析样本...")
    analyze_samples(SAMPLE_DIR, yara_rules, sigma_matchers)
    
    print("\n[3/3] 分析完成")

if __name__ == "__main__":
    main()

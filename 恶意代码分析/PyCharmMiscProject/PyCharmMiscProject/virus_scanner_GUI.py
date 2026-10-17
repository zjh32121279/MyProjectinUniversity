# virus_scanner_gui_tk.py
import sys
import os
import traceback
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# 导入你的Analyse.py模块
try:
    import Analyse

    # 创建必要的目录结构
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RULE_DIR = os.path.join(BASE_DIR, 'rule')
    SAMPLE_DIR = os.path.join(BASE_DIR, 'sample')

    # 确保目录存在
    os.makedirs(RULE_DIR, exist_ok=True)
    os.makedirs(SAMPLE_DIR, exist_ok=True)

    ANALYSE_AVAILABLE = True
    print("✅ Analyse模块加载成功")
except ImportError as e:
    print(f"⚠️ 警告: 无法导入Analyse模块: {e}")
    ANALYSE_AVAILABLE = False
except Exception as e:
    print(f"⚠️ 警告: 初始化失败: {e}")
    ANALYSE_AVAILABLE = False


class SimpleVirusScanner:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("病毒文件扫描器")
        self.root.geometry("500x400")
        self.root.resizable(False, False)

        # 设置窗口图标（可选）
        # self.root.iconbitmap('icon.ico')

        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 标题
        title_label = ttk.Label(
            main_frame,
            text="🛡️ 病毒文件扫描器",
            font=('Arial', 24, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 40), columnspan=2)

        # 按钮容器
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, pady=10, columnspan=2)

        # 按钮样式
        button_style = {
            'width': 20,
            'height': 2,
            'font': ('Arial', 12, 'bold')
        }

        # 选择文件按钮
        self.btn_file = tk.Button(
            button_frame,
            text="📁 选择文件",
            bg="#3498db",
            fg="white",
            command=self.select_file,
            **button_style
        )
        self.btn_file.grid(row=0, column=0, pady=10, padx=10)

        # 选择文件夹按钮
        self.btn_folder = tk.Button(
            button_frame,
            text="📂 选择文件夹",
            bg="#2ecc71",
            fg="white",
            command=self.select_folder,
            **button_style
        )
        self.btn_folder.grid(row=1, column=0, pady=10, padx=10)

        # 帮助按钮
        self.btn_help = tk.Button(
            button_frame,
            text="❓ 使用帮助",
            bg="#95a5a6",
            fg="white",
            command=self.show_help,
            **button_style
        )
        self.btn_help.grid(row=2, column=0, pady=10, padx=10)

        # 状态标签
        self.status_label = ttk.Label(
            main_frame,
            text="就绪 - 请选择要扫描的文件或文件夹",
            font=('Arial', 10)
        )
        self.status_label.grid(row=2, column=0, pady=(20, 0), columnspan=2)

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def select_file(self):
        """选择单个文件"""
        file_path = filedialog.askopenfilename(
            title="选择要扫描的文件",
            filetypes=[("所有文件", "*.*")]
        )

        if file_path:
            self.status_label.config(text=f"准备扫描: {os.path.basename(file_path)}")
            self.root.update()  # 更新UI
            # 开始扫描
            self.start_scan([file_path])

    def select_folder(self):
        """选择文件夹"""
        folder_path = filedialog.askdirectory(
            title="选择要扫描的文件夹"
        )

        if folder_path:
            # 获取文件夹下所有文件
            files = []
            for root, _, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    try:
                        if os.path.getsize(file_path) < 100 * 1024 * 1024:  # 限制100MB以内
                            files.append(file_path)
                    except:
                        continue

            if files:
                self.status_label.config(text=f"准备扫描文件夹: {len(files)} 个文件")
                self.root.update()  # 更新UI
                # 开始扫描
                self.start_scan(files)
            else:
                messagebox.showinfo("提示", "文件夹为空或所有文件超过100MB限制")

    def start_scan(self, file_list):
        """开始扫描文件"""
        # 创建结果窗口
        self.result_window = ResultWindow(file_list, self.root)
        self.status_label.config(text="扫描中...")

    def show_help(self):
        """显示帮助信息"""
        help_text = """🛡️ 病毒文件扫描器 - 使用帮助

一、主要功能
1. 📁 选择文件 - 扫描单个文件
2. 📂 选择文件夹 - 扫描整个文件夹

二、使用方法
1. 点击"选择文件"或"选择文件夹"按钮
2. 选择要扫描的目标
3. 查看扫描结果

三、扫描规则
• YARA规则检测：检测恶意代码特征
• Sigma规则检测：检测可疑行为模式
• 规则存放：项目下的 rule 文件夹

四、注意事项
• 大文件扫描可能需要较长时间
• 自动跳过超过100MB的大文件
• 扫描结果仅供参考"""

        help_window = tk.Toplevel(self.root)
        help_window.title("使用帮助")
        help_window.geometry("700x500")

        text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, font=('Arial', 11))
        text_widget.insert('1.0', help_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_close = ttk.Button(help_window, text="关闭", command=help_window.destroy)
        btn_close.pack(pady=10)

    def run(self):
        """运行程序"""
        self.root.mainloop()


class ResultWindow:
    """结果显示窗口"""

    def __init__(self, file_list, parent=None):
        self.file_list = file_list
        self.scan_results = []

        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title("扫描结果")
        self.window.geometry("900x700")

        self.setup_ui()
        self.start_scanning()

    def setup_ui(self):
        """设置界面"""
        # 主框架
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        title_label = ttk.Label(
            title_frame,
            text="📊 扫描结果详情",
            font=('Arial', 18, 'bold')
        )
        title_label.grid(row=0, column=0, sticky=tk.W)

        self.scan_status = ttk.Label(
            title_frame,
            text="正在扫描...",
            font=('Arial', 10, 'bold'),
            foreground='orange'
        )
        self.scan_status.grid(row=0, column=1, sticky=tk.E, padx=(20, 0))

        title_frame.columnconfigure(1, weight=1)

        # 统计信息栏
        stats_frame = ttk.Frame(main_frame, relief='ridge', padding="5")
        stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.total_label = ttk.Label(stats_frame, text="总文件数: 0")
        self.total_label.grid(row=0, column=0, padx=5)

        self.scanned_label = ttk.Label(stats_frame, text="已扫描: 0")
        self.scanned_label.grid(row=0, column=1, padx=5)

        self.threat_label = ttk.Label(stats_frame, text="发现威胁: 0")
        self.threat_label.grid(row=0, column=2, padx=5)

        self.safe_label = ttk.Label(stats_frame, text="安全文件: 0")
        self.safe_label.grid(row=0, column=3, padx=5)

        self.error_label = ttk.Label(stats_frame, text="扫描失败: 0")
        self.error_label.grid(row=0, column=4, padx=5)

        # 结果文本框
        text_frame = ttk.Frame(main_frame)
        text_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        self.result_text = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            width=100,
            height=30
        )
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))

        self.btn_save = ttk.Button(
            button_frame,
            text="💾 保存结果",
            command=self.save_results,
            state='disabled'
        )
        self.btn_save.grid(row=0, column=0, padx=5)

        self.btn_copy = ttk.Button(
            button_frame,
            text="📋 复制结果",
            command=self.copy_results,
            state='disabled'
        )
        self.btn_copy.grid(row=0, column=1, padx=5)

        ttk.Label(button_frame, text="").grid(row=0, column=2, padx=150)  # 空标签作为间隔

        self.btn_close = ttk.Button(
            button_frame,
            text="❌ 关闭窗口",
            command=self.window.destroy
        )
        self.btn_close.grid(row=0, column=3, padx=5)

        # 配置网格权重
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

    def start_scanning(self):
        """开始扫描"""
        # 更新统计信息
        self.total_label.config(text=f"总文件数: {len(self.file_list)}")

        # 显示初始信息
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.result_text.insert(tk.END, "=" * 80 + "\n")
        self.result_text.insert(tk.END, "🛡️ 病毒文件扫描器 - 扫描报告\n")
        self.result_text.insert(tk.END, "=" * 80 + "\n")
        self.result_text.insert(tk.END, f"📅 扫描开始时间: {current_time}\n")
        self.result_text.insert(tk.END, f"📁 扫描目标数量: {len(self.file_list)} 个文件\n")
        self.result_text.insert(tk.END, "🔍 扫描引擎: YARA规则 + Sigma规则\n")
        self.result_text.insert(tk.END, "-" * 80 + "\n")
        self.result_text.insert(tk.END, "开始扫描...\n\n")

        # 在单独的线程中运行扫描
        self.scanner_thread = ScannerThread(self.file_list)
        self.scanner_thread.result_callback = self.update_result
        self.scanner_thread.progress_callback = self.update_progress
        self.scanner_thread.finish_callback = self.scan_finished
        self.scanner_thread.start()

    def update_result(self, result_data):
        """更新扫描结果"""
        file_path = result_data['file']
        file_name = result_data.get('file_name', os.path.basename(file_path))
        status = result_data['status']
        threat_info = result_data.get('threat_info', '')

        # 添加到结果列表
        self.scan_results.append(result_data)

        # 更新统计
        self.scanned_label.config(text=f"已扫描: {len(self.scan_results)}")

        # 根据状态显示
        if status == "threat":
            current = int(self.threat_label.cget("text").split(": ")[1])
            self.threat_label.config(text=f"发现威胁: {current + 1}")

            self.result_text.insert(tk.END, f"❌ [{len(self.scan_results)}/{len(self.file_list)}] 发现威胁!\n")
            self.result_text.insert(tk.END, f"   文件: {file_name}\n")
            self.result_text.insert(tk.END, f"   路径: {file_path}\n")
            self.result_text.insert(tk.END, f"   威胁类型: {threat_info}\n")

            # 显示YARA匹配详情
            yara_matches = result_data.get('yara_matches', [])
            if yara_matches:
                self.result_text.insert(tk.END, f"   🔍 YARA规则命中:\n")
                for match in yara_matches[:3]:
                    rule_name = match.get('rule', '未知规则')
                    namespace = match.get('namespace', '未知')
                    self.result_text.insert(tk.END, f"      - {rule_name} ({namespace})\n")

            self.result_text.insert(tk.END, "\n")

        elif status == "suspicious":
            self.result_text.insert(tk.END, f"⚠️  [{len(self.scan_results)}/{len(self.file_list)}] 发现可疑行为\n")
            self.result_text.insert(tk.END, f"   文件: {file_name}\n")
            self.result_text.insert(tk.END, f"   路径: {file_path}\n")
            self.result_text.insert(tk.END, f"   可疑原因: {threat_info}\n\n")

        elif status == "safe":
            current = int(self.safe_label.cget("text").split(": ")[1])
            self.safe_label.config(text=f"安全文件: {current + 1}")

            self.result_text.insert(tk.END, f"✅ [{len(self.scan_results)}/{len(self.file_list)}] 扫描完成\n")
            self.result_text.insert(tk.END, f"   文件: {file_name}\n")
            self.result_text.insert(tk.END, f"   路径: {file_path}\n")
            self.result_text.insert(tk.END, f"   状态: {threat_info}\n\n")

        elif status == "error":
            current = int(self.error_label.cget("text").split(": ")[1])
            self.error_label.config(text=f"扫描失败: {current + 1}")

            self.result_text.insert(tk.END, f"⚠️  [{len(self.scan_results)}/{len(self.file_list)}] 扫描失败\n")
            self.result_text.insert(tk.END, f"   文件: {file_name}\n")
            self.result_text.insert(tk.END, f"   路径: {file_path}\n")
            self.result_text.insert(tk.END, f"   错误: {threat_info}\n\n")

        # 滚动到底部
        self.result_text.see(tk.END)
        self.window.update()

    def update_progress(self, progress):
        """更新进度"""
        self.scan_status.config(text=f"扫描进度: {progress}%")

    def scan_finished(self):
        """扫描完成"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self.result_text.insert(tk.END, "\n" + "=" * 80 + "\n")
        self.result_text.insert(tk.END, "📋 扫描完成摘要\n")
        self.result_text.insert(tk.END, "=" * 80 + "\n")

        # 统计
        threat_files = [r for r in self.scan_results if r['status'] == 'threat']
        safe_files = [r for r in self.scan_results if r['status'] == 'safe']
        error_files = [r for r in self.scan_results if r['status'] == 'error']

        if threat_files:
            self.result_text.insert(tk.END, "\n🚨 发现威胁的文件：\n")
            for result in threat_files[:10]:  # 最多显示10个
                self.result_text.insert(tk.END, f"  • {os.path.basename(result['file'])}\n")
                self.result_text.insert(tk.END, f"    路径: {result['file']}\n")
                if len(threat_files) > 10:
                    self.result_text.insert(tk.END, f"    ... 还有{len(threat_files) - 10}个文件\n")
                    break
        else:
            self.result_text.insert(tk.END, "\n✅ 未发现威胁文件\n")

        self.result_text.insert(tk.END, "\n" + "-" * 80 + "\n")
        self.result_text.insert(tk.END, "📊 扫描统计：\n")
        self.result_text.insert(tk.END, f"  总文件数: {len(self.file_list)}\n")
        self.result_text.insert(tk.END, f"  成功扫描: {len(safe_files)}\n")
        self.result_text.insert(tk.END, f"  发现威胁: {len(threat_files)}\n")
        self.result_text.insert(tk.END, f"  扫描失败: {len(error_files)}\n")
        self.result_text.insert(tk.END, f"📅 完成时间: {current_time}\n")

        # 更新状态
        self.scan_status.config(text="扫描完成", foreground='green')

        # 启用保存和复制按钮
        self.btn_save.config(state='normal')
        self.btn_copy.config(state='normal')

        self.result_text.see(tk.END)

    def save_results(self):
        """保存结果到文件"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"病毒扫描结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if file_path:
            try:
                content = self.result_text.get("1.0", tk.END)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                messagebox.showinfo("保存成功", f"扫描结果已保存到：\n{file_path}")
                self.result_text.insert(tk.END, f"\n💾 结果已保存到: {file_path}\n")
                self.result_text.see(tk.END)
            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存文件：{str(e)}")

    def copy_results(self):
        """复制结果到剪贴板"""
        content = self.result_text.get("1.0", tk.END)
        self.window.clipboard_clear()
        self.window.clipboard_append(content)
        messagebox.showinfo("复制成功", "扫描结果已复制到剪贴板")


class ScannerThread(threading.Thread):
    """扫描线程"""

    def __init__(self, file_list):
        super().__init__()
        self.file_list = file_list
        self.yara_rules = None
        self.sigma_matchers = []
        self.rules_loaded = False
        self.result_callback = None
        self.progress_callback = None
        self.finish_callback = None

    def load_rules(self):
        """加载YARA和Sigma规则"""
        try:
            if not ANALYSE_AVAILABLE:
                return False, "Analyse模块不可用"

            # 检查规则目录是否存在
            if not os.path.exists(RULE_DIR):
                return False, f"规则目录不存在: {RULE_DIR}"

            print(f"正在从 {RULE_DIR} 加载规则...")

            # 加载YARA规则
            self.yara_rules = Analyse.load_yara_rules(RULE_DIR)
            if self.yara_rules is None:
                return False, "YARA规则加载失败"
            print("✅ YARA规则加载成功")

            # 加载Sigma规则
            self.sigma_matchers = Analyse.load_sigma_rules(RULE_DIR)
            print(f"✅ Sigma规则加载成功: {len(self.sigma_matchers)} 个规则")

            self.rules_loaded = True
            return True, "规则加载成功"

        except Exception as e:
            error_msg = f"规则加载失败: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return False, error_msg

    def scan_single_file(self, file_path):
        """扫描单个文件"""
        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)

            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_content = f.read()

            result = {
                'file': file_path,
                'file_name': file_name,
                'file_size': file_size,
                'yara_matches': [],
                'sigma_matches': [],
                'status': 'unknown'
            }

            # 1. YARA扫描
            if self.yara_rules:
                try:
                    yara_matches = self.yara_rules.match(data=file_content)
                    if yara_matches:
                        result['yara_matches'] = []
                        for match in yara_matches:
                            match_info = {
                                'rule': match.rule,
                                'namespace': match.namespace
                            }
                            # 添加可选的属性
                            try:
                                if hasattr(match, 'tags'):
                                    match_info['tags'] = match.tags
                            except:
                                pass
                            try:
                                if hasattr(match, 'meta'):
                                    match_info['meta'] = match.meta
                            except:
                                pass
                            result['yara_matches'].append(match_info)
                except Exception as e:
                    result['yara_error'] = f"YARA扫描错误: {str(e)}"

            # 2. Sigma扫描
            sigma_hits = []
            for matcher in self.sigma_matchers:
                try:
                    hits = matcher.match(file_content)
                    if hits:
                        sigma_info = {
                            'title': matcher.data.get('title', os.path.basename(matcher.rule_path)),
                            'keywords': hits[:5],
                            'description': matcher.data.get('description', ''),
                            'severity': matcher.data.get('level', '未知')
                        }
                        sigma_hits.append(sigma_info)
                except Exception as e:
                    # 忽略单个Sigma规则的错误
                    pass

            if sigma_hits:
                result['sigma_matches'] = sigma_hits

            # 3. 判断扫描结果状态
            if result.get('yara_error'):
                result['status'] = 'error'
                result['threat_info'] = result['yara_error']
            elif result['yara_matches']:
                result['status'] = 'threat'
                # 提取威胁信息
                threats = []
                for match in result['yara_matches']:
                    threat_name = match.get('meta', {}).get('description', match['rule'])
                    threats.append(threat_name)
                result['threat_info'] = " | ".join(threats[:3])
            elif result['sigma_matches']:
                result['status'] = 'suspicious'
                sigmas = [s['title'] for s in result['sigma_matches']]
                result['threat_info'] = f"Sigma规则匹配: {', '.join(sigmas[:2])}"
            else:
                result['status'] = 'safe'
                result['threat_info'] = '安全'

            return result

        except Exception as e:
            error_result = {
                'file': file_path,
                'file_name': os.path.basename(file_path),
                'status': 'error',
                'threat_info': f"扫描异常: {str(e)}",
                'error': str(e)
            }
            return error_result

    def run(self):
        """执行扫描"""
        if not ANALYSE_AVAILABLE:
            if self.result_callback:
                self.result_callback({
                    'file': '',
                    'file_name': '系统错误',
                    'status': 'error',
                    'threat_info': 'Analyse.py模块不可用，请确保文件存在且依赖已安装'
                })
            if self.finish_callback:
                self.finish_callback()
            return

        # 1. 加载规则
        load_success, load_message = self.load_rules()
        if not load_success:
            if self.result_callback:
                self.result_callback({
                    'file': '',
                    'file_name': '规则加载失败',
                    'status': 'error',
                    'threat_info': load_message
                })

        # 2. 扫描每个文件
        total_files = len(self.file_list)
        scanned_count = 0

        for i, file_path in enumerate(self.file_list):
            try:
                # 检查文件是否存在
                if not os.path.exists(file_path):
                    if self.result_callback:
                        self.result_callback({
                            'file': file_path,
                            'file_name': os.path.basename(file_path),
                            'status': 'error',
                            'threat_info': '文件不存在'
                        })
                    continue

                # 检查文件大小（限制为100MB）
                file_size = os.path.getsize(file_path)
                if file_size > 100 * 1024 * 1024:  # 100MB
                    if self.result_callback:
                        self.result_callback({
                            'file': file_path,
                            'file_name': os.path.basename(file_path),
                            'status': 'error',
                            'threat_info': f'文件过大 ({file_size // 1024 // 1024}MB > 100MB限制)'
                        })
                    continue

                # 扫描文件
                if self.rules_loaded:
                    result = self.scan_single_file(file_path)
                else:
                    # 规则加载失败，返回错误
                    result = {
                        'file': file_path,
                        'file_name': os.path.basename(file_path),
                        'status': 'error',
                        'threat_info': '规则未加载，无法扫描'
                    }

                # 发送结果
                if self.result_callback:
                    self.result_callback(result)

                scanned_count += 1

                # 更新进度
                if self.progress_callback:
                    progress = int((i + 1) / total_files * 100)
                    self.progress_callback(progress)

                # 稍微延迟，避免界面卡顿
                time.sleep(0.01)

            except Exception as e:
                # 捕获所有异常
                error_result = {
                    'file': file_path,
                    'file_name': os.path.basename(file_path) if file_path else '未知文件',
                    'status': 'error',
                    'threat_info': f"处理失败: {str(e)}"
                }
                if self.result_callback:
                    self.result_callback(error_result)
                traceback.print_exc()

        if self.finish_callback:
            self.finish_callback()


def main():
    """主函数"""
    # 检查依赖
    if not ANALYSE_AVAILABLE:
        print("❌ 错误: 无法加载Analyse.py模块")
        print("请确保:")
        print("1. Analyse.py文件在当前目录")
        print("2. 已安装依赖: pip install yara-python pyyaml")
        response = messagebox.askyesno("错误",
                                       "无法加载Analyse.py模块，是否继续使用模拟扫描？\n\n"
                                       "是 - 使用模拟数据继续\n"
                                       "否 - 退出程序")
        if not response:
            return

    # 创建并运行程序
    app = SimpleVirusScanner()
    app.run()


if __name__ == "__main__":
    main()
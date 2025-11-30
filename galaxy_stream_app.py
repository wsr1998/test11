"""
Galaxy Stream Identification Web App
=====================================
独立的 Web 应用,用于标注星系图像中的恒星流

使用方法:
    streamlit run galaxy_stream_app.py

浏览器会自动打开,显示交互界面
"""

import streamlit as st
import pandas as pd
import requests
from PIL import Image, ImageOps
from io import BytesIO
import json
from pathlib import Path
from datetime import datetime
from streamlit_shortcuts import add_shortcuts

# 页面配置
st.set_page_config(
    page_title="Galaxy Stream Identifier",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 session state
if 'galaxy_data' not in st.session_state:
    st.session_state.galaxy_data = None
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'is_inverted' not in st.session_state:
    st.session_state.is_inverted = False
if 'save_file' not in st.session_state:
    st.session_state.save_file = None
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'auto_save_interval' not in st.session_state:
    st.session_state.auto_save_interval = 5
if 'labels_since_save' not in st.session_state:
    st.session_state.labels_since_save = 0
if 'save_directory' not in st.session_state:
    st.session_state.save_directory = str(Path.cwd())
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False


def load_csv_data(uploaded_file):
    """加载 CSV 文件"""
    try:
        df = pd.read_csv(uploaded_file)
        if 'image_url' not in df.columns:
            st.error("❌ CSV 文件必须包含 'image_url' 列!")
            return None
        return df
    except Exception as e:
        st.error(f"❌ 加载 CSV 失败: {e}")
        return None


def load_existing_labels(file_path):
    """加载已有的标注结果"""
    try:
        if Path(file_path).exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
    except Exception as e:
        st.warning(f"⚠️ 无法加载已有标注: {e}")
    return {}


def save_results(file_path, results):
    """保存标注结果"""
    try:
        with open(file_path, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ 保存失败: {e}")
        return False


def load_image_from_url(url):
    """从 URL 加载图像"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        return img
    except Exception as e:
        st.error(f"❌ 加载图像失败: {e}")
        return None


def get_summary_stats(results):
    """获取统计摘要"""
    total = len(st.session_state.galaxy_data) if st.session_state.galaxy_data is not None else 0
    classified = len(results)
    has_stream = sum(1 for r in results.values() if r['classification'] == 'has_stream')
    no_stream = sum(1 for r in results.values() if r['classification'] == 'no_stream')
    skipped = sum(1 for r in results.values() if r['classification'] == 'skipped')
    
    return {
        'total': total,
        'classified': classified,
        'unclassified': total - classified,
        'has_stream': has_stream,
        'no_stream': no_stream,
        'skipped': skipped
    }


# ============================================================================
# 侧边栏 - 文件加载和配置
# ============================================================================

st.sidebar.title("🌌 Galaxy Stream Identifier")
st.sidebar.markdown("---")

# 步骤 1: 上传 CSV 文件
st.sidebar.header("📁 步骤 1: 加载数据")
uploaded_file = st.sidebar.file_uploader(
    "选择包含星系数据的 CSV 文件",
    type=['csv'],
    help="CSV 文件必须包含 'image_url' 列"
)

if uploaded_file is not None and not st.session_state.data_loaded:
    df = load_csv_data(uploaded_file)
    if df is not None:
        st.session_state.galaxy_data = df
        st.sidebar.success(f"✅ 已加载 {len(df)} 个星系")
        
        # 显示数据预览
        with st.sidebar.expander("📊 数据预览"):
            st.dataframe(df.head(), use_container_width=True)

# 步骤 2: 配置保存文件
st.sidebar.header("💾 步骤 2: 配置保存")
if st.session_state.galaxy_data is not None:
    
    # 2.1 加载已有标注文件
    st.sidebar.markdown("**2.1 加载已有标注 (可选)**")
    existing_file = st.sidebar.file_uploader(
        "上传 JSON 标注文件",
        type=['json'],
        help="继续之前的标注工作",
        key="load_existing"
    )
    
    if existing_file is not None:
        try:
            content = existing_file.read().decode('utf-8')
            data = json.loads(content)
            st.session_state.results = {int(k): v for k, v in data.items()}
            st.sidebar.success(f"✅ 已加载 {len(st.session_state.results)} 条标注")
            # 使用上传文件的名称
            st.session_state.save_file = Path(st.session_state.save_directory) / existing_file.name
            
            # 重置自动保存计数器
            st.session_state.labels_since_save = 0
            
            # 自动跳转到第一个未标注的星系
            if st.session_state.galaxy_data is not None:
                total_galaxies = len(st.session_state.galaxy_data)
                for i in range(total_galaxies):
                    if i not in st.session_state.results:
                        st.session_state.current_index = i
                        st.sidebar.info(f"💡 已跳转到第一个未标注的星系 (#{i + 1})")
                        break
                else:
                    # 所有都已标注，跳转到最后一个
                    st.session_state.current_index = total_galaxies - 1
                    st.sidebar.info("💡 所有星系已标注完成")
        except Exception as e:
            st.sidebar.error(f"❌ 加载失败: {e}")
    
    st.sidebar.markdown("---")
    
    # 2.2 自动保存间隔
    st.sidebar.markdown("**2.2 自动保存设置**")
    st.session_state.auto_save_interval = st.sidebar.number_input(
        "每标注几个自动保存",
        min_value=1,
        max_value=50,
        value=st.session_state.auto_save_interval,
        step=1,
        help="标注指定数量后自动保存结果"
    )
    
    st.sidebar.markdown("---")
    
    # 2.3 新建保存文件
    st.sidebar.markdown("**2.3 新建保存文件**")
    
    # 获取常用目录
    current_dir = Path.cwd()
    home_dir = Path.home()
    data_dir = current_dir / "Data"
    parent_dir = current_dir.parent
    
    # 构建目录选项
    dir_options = {
        f"📁 当前目录: {current_dir}": str(current_dir),
        f"🏠 主目录: {home_dir}": str(home_dir),
    }
    
    if data_dir.exists():
        dir_options[f"📊 Data目录: {data_dir}"] = str(data_dir)
    
    dir_options[f"⬆️ 上级目录: {parent_dir}"] = str(parent_dir)
    dir_options["✏️ 自定义路径..."] = "custom"
    
    # 选择目录方式
    selected_option = st.sidebar.selectbox(
        "选择保存目录",
        options=list(dir_options.keys()),
        help="选择常用目录或自定义路径"
    )
    
    selected_path = dir_options[selected_option]
    
    # 如果选择自定义,显示文本输入
    if selected_path == "custom":
        save_dir_input = st.sidebar.text_input(
            "输入自定义目录路径",
            value=st.session_state.save_directory,
            help="输入保存目录的完整路径"
        )
        
        # 验证自定义路径
        if save_dir_input:
            custom_path = Path(save_dir_input)
            if custom_path.exists() and custom_path.is_dir():
                st.session_state.save_directory = str(custom_path)
                st.sidebar.success("✅ 有效目录")
            else:
                st.sidebar.error("❌ 目录不存在")
    else:
        # 使用选中的预设路径
        st.session_state.save_directory = selected_path
        st.sidebar.info(f"📂 使用: {selected_path}")
    
    # 输入文件名
    if st.session_state.save_file is None or existing_file is None:
        save_filename = st.sidebar.text_input(
            "保存文件名",
            value="galaxy_labels.json",
            help="仅输入文件名(如: my_labels.json)"
        )
        
        if save_filename:
            st.session_state.save_file = Path(st.session_state.save_directory) / save_filename
    
    # 显示完整保存路径
    if st.session_state.save_file:
        st.sidebar.info(f"💾 完整保存路径:\n`{st.session_state.save_file}`")

# 步骤 3: 开始标注
st.sidebar.header("🚀 步骤 3: 开始标注")
if st.session_state.galaxy_data is not None and st.session_state.save_file is not None:
    if st.sidebar.button("▶️ 开始/继续标注", type="primary"):
        st.session_state.data_loaded = True
        st.rerun()

st.sidebar.markdown("---")

# 统计信息
if st.session_state.data_loaded:
    st.sidebar.header("📊 统计信息")
    stats = get_summary_stats(st.session_state.results)
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("总数", stats['total'])
        st.metric("✅ Has Stream", stats['has_stream'])
    with col2:
        st.metric("已标注", stats['classified'])
        st.metric("❌ No Stream", stats['no_stream'])
    
    st.sidebar.metric("⏭️ Skipped", stats['skipped'])
    
    # 进度条
    progress = stats['classified'] / stats['total'] if stats['total'] > 0 else 0
    st.sidebar.progress(progress, text=f"进度: {progress*100:.1f}%")


# ============================================================================
# 主界面 - 标注界面
# ============================================================================

if not st.session_state.data_loaded:
    # 欢迎页面
    st.title("🌌 Galaxy Stream Identification Tool")
    st.markdown("---")
    
    st.markdown("""
    ## 欢迎使用星系恒星流标注工具!
    
    ### 📋 使用步骤:
    
    1. **📁 加载数据**: 在左侧上传包含星系数据的 CSV 文件
       - CSV 必须包含 `image_url` 列
       - 可选列: `subject_id`, `hash` 等元数据
    
    2. **💾 配置保存**: 设置保存文件的位置和名称
       - 结果将保存为 JSON 格式
       - 可以随时加载之前的标注继续工作
    
    3. **🚀 开始标注**: 点击"开始/继续标注"按钮
       - 查看星系图像
       - 判断是否包含恒星流
       - 使用导航按钮浏览
    
    ### ✨ 功能特性:
    
    - ✅ 交互式界面,操作简单
    - ✅ 图像反转功能 (便于观察暗弱特征)
    - ✅ 自动保存标注结果
    - ✅ 支持断点续传
    - ✅ 实时统计显示
    - ✅ 标注锁定 (防止误操作)
    
    ---
    
    👈 **请从左侧开始操作**
    """)

else:
    # 标注界面
    df = st.session_state.galaxy_data
    idx = st.session_state.current_index
    
    # 检查索引有效性
    if idx >= len(df):
        st.success("🎉 所有星系已浏览完毕!")
        st.balloons()
        
        # 显示最终统计
        st.header("📊 最终统计")
        stats = get_summary_stats(st.session_state.results)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总数", stats['total'])
        with col2:
            st.metric("已标注", stats['classified'])
        with col3:
            st.metric("Has Stream", stats['has_stream'])
        with col4:
            st.metric("No Stream", stats['no_stream'])
        
        # 导出选项
        st.header("💾 导出结果")
        
        if st.button("保存为 JSON"):
            if save_results(st.session_state.save_file, st.session_state.results):
                st.success(f"✅ 已保存到: {st.session_state.save_file}")
        
        if st.button("导出为 CSV"):
            results_df = pd.DataFrame(list(st.session_state.results.values()))
            csv_file = st.session_state.save_file.with_suffix('.csv')
            results_df.to_csv(csv_file, index=False)
            st.success(f"✅ 已导出到: {csv_file}")
        
        if st.button("🔄 重新开始"):
            st.session_state.current_index = 0
            st.rerun()
        
    else:
        # 获取当前星系数据
        current_row = df.iloc[idx]
        url = current_row['image_url']
        
        # 检查是否已标注
        is_labeled = idx in st.session_state.results
        
        # 标题和进度
        st.title(f"🌌 Galaxy {idx + 1} of {len(df)}")
        
        # 进度条
        progress = idx / len(df)
        st.progress(progress, text=f"进度: {idx + 1}/{len(df)}")
        
        # 显示元数据
        with st.expander("📋 星系元数据"):
            metadata_cols = [col for col in df.columns if col != 'image_url']
            if metadata_cols:
                for col in metadata_cols:
                    st.text(f"{col}: {current_row[col]}")
            else:
                st.info("无额外元数据")
        
        st.markdown("---")
        
        # 图像显示区域
        col_img, col_controls = st.columns([2, 1])
        
        with col_img:
            # 加载图像
            with st.spinner("加载图像中..."):
                img = load_image_from_url(url)
            
            if img is not None:
                # 图像反转
                if st.session_state.is_inverted:
                    if img.mode == 'RGBA':
                        r, g, b, a = img.split()
                        rgb = Image.merge('RGB', (r, g, b))
                        inverted_rgb = ImageOps.invert(rgb)
                        r2, g2, b2 = inverted_rgb.split()
                        img = Image.merge('RGBA', (r2, g2, b2, a))
                    else:
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        img = ImageOps.invert(img)
                
                st.image(img, use_container_width=True, caption=f"Galaxy {idx + 1}")
        
        with col_controls:
            st.header("🎮 控制面板")
            
            # 编辑模式开关
            st.subheader("🔓 编辑模式")
            edit_mode = st.toggle(
                "启用编辑模式",
                value=st.session_state.edit_mode,
                key="edit_mode_toggle",
                help="开启后可以修改已标注的结果"
            )
            st.session_state.edit_mode = edit_mode
            
            if edit_mode:
                st.warning("⚠️ 编辑模式已启用 - 可修改已标注结果")
            else:
                st.info("🔒 编辑模式已关闭 - 已标注结果被锁定")
            
            st.markdown("---")
            
            # 图像控制
            st.subheader("🖼️ 图像控制")
            if st.button("🔄 反转图像", use_container_width=True, key="invert_btn"):
                st.session_state.is_inverted = not st.session_state.is_inverted
                st.rerun()
            
            if st.session_state.is_inverted:
                st.info("📍 当前: 反转模式")
            else:
                st.info("📍 当前: 正常模式")
            
            st.markdown("---")
            
            # 分类按钮
            st.subheader("🏷️ 分类")
            
            # 检查是否已标注和编辑模式状态
            if is_labeled and not st.session_state.edit_mode:
                # 显示已有标注（锁定状态）
                result = st.session_state.results[idx]
                classification = result['classification']
                timestamp = result.get('timestamp', 'Unknown')
                
                if classification == 'has_stream':
                    st.success("✅ Has Stream")
                elif classification == 'no_stream':
                    st.error("❌ No Stream")
                else:
                    st.warning("⏭️ Skipped")
                
                st.caption(f"标注时间: {timestamp}")
                st.info("🔒 已标注,不可修改 (开启编辑模式以更改)")
                
            else:
                # 显示分类按钮（未标注 或 编辑模式已启用）
                if is_labeled and st.session_state.edit_mode:
                    st.warning("⚠️ 编辑模式已启用 - 可以修改此标注")
                    # 显示当前标注
                    result = st.session_state.results[idx]
                    classification = result['classification']
                    if classification == 'has_stream':
                        st.info("当前: ✅ Has Stream")
                    elif classification == 'no_stream':
                        st.info("当前: ❌ No Stream")
                    else:
                        st.info("当前: ⏭️ Skipped")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("✅ Has\nStream", use_container_width=True, type="primary", key="has_stream_btn"):
                        result = {
                            'url': url,
                            'classification': 'has_stream',
                            'index': idx,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'metadata': current_row.to_dict()
                        }
                        if is_labeled:
                            result['edited'] = True
                        
                        st.session_state.results[idx] = result
                        
                        # 如果是编辑，立即保存；否则使用自动保存
                        if is_labeled and st.session_state.edit_mode:
                            if save_results(st.session_state.save_file, st.session_state.results):
                                st.success("✅ 已修改为 Has Stream 并立即保存")
                        else:
                            # 新标注更新计数器
                            st.session_state.labels_since_save += 1
                            
                            # 自动保存逻辑
                            if st.session_state.labels_since_save >= st.session_state.auto_save_interval:
                                save_results(st.session_state.save_file, st.session_state.results)
                                st.session_state.labels_since_save = 0
                                st.success("✅ 已标注: Has Stream (已自动保存)")
                            else:
                                st.success(f"✅ 已标注: Has Stream ({st.session_state.labels_since_save}/{st.session_state.auto_save_interval})")
                        st.rerun()
                
                with col2:
                    if st.button("❌ No\nStream", use_container_width=True, key="no_stream_btn"):
                        result = {
                            'url': url,
                            'classification': 'no_stream',
                            'index': idx,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'metadata': current_row.to_dict()
                        }
                        if is_labeled:
                            result['edited'] = True
                        
                        st.session_state.results[idx] = result
                        
                        # 如果是编辑，立即保存；否则使用自动保存
                        if is_labeled and st.session_state.edit_mode:
                            if save_results(st.session_state.save_file, st.session_state.results):
                                st.success("✅ 已修改为 No Stream 并立即保存")
                        else:
                            # 新标注更新计数器
                            st.session_state.labels_since_save += 1
                            
                            # 自动保存逻辑
                            if st.session_state.labels_since_save >= st.session_state.auto_save_interval:
                                save_results(st.session_state.save_file, st.session_state.results)
                                st.session_state.labels_since_save = 0
                                st.success("✅ 已标注: No Stream (已自动保存)")
                            else:
                                st.success(f"✅ 已标注: No Stream ({st.session_state.labels_since_save}/{st.session_state.auto_save_interval})")
                        st.rerun()
                
                with col3:
                    if st.button("⏭️ Skip", use_container_width=True, key="skip_btn"):
                        result = {
                            'url': url,
                            'classification': 'skipped',
                            'index': idx,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'metadata': current_row.to_dict()
                        }
                        if is_labeled:
                            result['edited'] = True
                        
                        st.session_state.results[idx] = result
                        
                        # 如果是编辑，立即保存；否则使用自动保存
                        if is_labeled and st.session_state.edit_mode:
                            if save_results(st.session_state.save_file, st.session_state.results):
                                st.warning("⏭️ 已修改为 Skipped 并立即保存")
                        else:
                            # 新标注更新计数器
                            st.session_state.labels_since_save += 1
                            
                            # 自动保存逻辑
                            if st.session_state.labels_since_save >= st.session_state.auto_save_interval:
                                save_results(st.session_state.save_file, st.session_state.results)
                                st.session_state.labels_since_save = 0
                                st.warning("⏭️ 已跳过 (已自动保存)")
                            else:
                                st.warning(f"⏭️ 已跳过 ({st.session_state.labels_since_save}/{st.session_state.auto_save_interval})")
                        st.rerun()
                
                if is_labeled and st.session_state.edit_mode:
                    st.caption("修改将立即保存")
                else:
                    st.caption("请选择分类")
        
        st.markdown("---")
        
        # 导航按钮
        col_prev, col_next = st.columns(2)
        
        with col_prev:
            if st.button("⬅️ 上一个", use_container_width=True, disabled=(idx == 0), key="prev_btn"):
                st.session_state.current_index = max(0, idx - 1)
                st.session_state.is_inverted = False
                st.rerun()
        
        with col_next:
            # 修改禁用条件：到达最后一个 或者 当前未标注
            next_disabled = (idx >= len(df) - 1) or not is_labeled
            next_btn_text = "下一个 ➡️" if is_labeled else "下一个 ➡️ (需先标注)"
            if st.button(next_btn_text, use_container_width=True, disabled=next_disabled, type="primary", key="next_btn"):
                st.session_state.current_index = min(len(df) - 1, idx + 1)
                st.session_state.is_inverted = False
                st.rerun()
        
        # 状态提示
        if not is_labeled:
            st.warning("⚠️ 警告: 请先分类当前星系才能继续到下一个")
        
        # 快捷键提示
        with st.expander("⌨️ 快捷键说明"):
            st.markdown("""
            - **E**: 切换编辑模式
            - **I**: 反转图像
            - **Y**: 标注为 Has Stream
            - **N**: 标注为 No Stream
            - **S**: 跳过当前图像
            - **←**: 上一个星系
            - **→**: 下一个星系
            """)
        
        # 添加快捷键支持 - 移到这里以确保所有按钮都已渲染
        # 根据当前状态动态调整快捷键
        shortcut_config = {
            "edit_mode_toggle": "e",      # E键切换编辑模式
            "invert_btn": "i",            # I键反转图像
            "prev_btn": "arrowleft",      # 左箭头上一个
        }
        
        # 只有在未标注或编辑模式开启时才启用分类快捷键
        if not is_labeled or st.session_state.edit_mode:
            shortcut_config["has_stream_btn"] = "y"   # Y键标注为Has Stream
            shortcut_config["no_stream_btn"] = "n"    # N键标注为No Stream
            shortcut_config["skip_btn"] = "s"         # S键跳过
        
        # 只有在已标注时才启用下一个快捷键（已移除，现在自动前进）
        # if is_labeled and idx < len(df) - 1:
        #     shortcut_config["next_btn"] = "arrowright"  # 右箭头下一个
        
        add_shortcuts(**shortcut_config)


# ============================================================================
# 底部信息
# ============================================================================

st.markdown("---")
st.caption("Galaxy Stream Identification Tool v1.0 | Powered by Streamlit")

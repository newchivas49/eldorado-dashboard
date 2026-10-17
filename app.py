import streamlit as st
import pandas as pd
import requests
import json
import datetime

# ---------------------------------------------------------
# 1. إعدادات الصفحة الأساسية (Page Config)
# ---------------------------------------------------------
st.set_page_config(
    page_title="لوحة تحكم إلدورادو",
    page_icon="📊",
    layout="wide"
)

# عنوان الصفحة الرئيسي
st.title("📊 لوحة تحكم بائع إلدورادو (Eldorado Dashboard)")

# ---------------------------------------------------------
# 2. القائمة الجانبية (Sidebar & Settings)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ إعدادات الحساب والربط")
    st.caption("قم بإدخال بيانات الاتصال لإدارة المتجر وتلقي التنبيهات المباشرة.")
    
    # اختيار وضع جلب البيانات (بيانات تجريبية أو اتصال حي)
    data_source_mode = st.radio(
        "مصدر البيانات:",
        ["بيانات تجريبية (Demo)", "اتصال حي بـ Eldorado API"],
        index=0,
        help="اختر البيانات التجريبية للاختبار أو الاتصال الحي الحقيقي بحسابك."
    )

    # حقل نصي مخفي لمفتاح API الخاص بإلدورادو
    eldorado_api_key = st.text_input(
        "Eldorado API Key / Bearer Token",
        type="password",
        help="أدخل مفتاح API أو الـ Bearer Token الخاص بحسابك على Eldorado.gg لجلب الطلبات الحقيقية."
    )
    
    # خيار لتحديد رابط نقطة نهاية API الحقيقية
    with st.expander("🌐 إعدادات نقطة نهاية API (متقدم)"):
        eldorado_api_endpoint = st.text_input(
            "رابط نقطة النهاية (Orders Endpoint)",
            value="https://eldorado.gg/api/orders",
            help="عنوان API الخاص بجلب الطلبات للبائع من منصة إلدورادو"
        )

    st.divider()
    
    st.subheader("🔔 إعدادات تنبيهات ديسكورد")
    # حقل نصي مخفي لرابط Discord Webhook
    discord_webhook_url = st.text_input(
        "Discord Webhook URL",
        type="password",
        help="أدخل رابط Webhook لقناة ديسكورد لتلقي الإشعارات."
    )
    
    # حقل نصي عادي لمعرف المستخدم في ديسكورد
    discord_user_id = st.text_input(
        "Discord User ID",
        help="أدخل معرف المستخدم (User ID) ليتم عمل Mention لك عند وصول إشعار."
    )
    
    # صناديق اختيار لتفعيل أنواع الإشعارات (مفعلة افتراضياً)
    notify_new_order = st.checkbox(
        "إشعارات الطلبات الجديدة (New Order)",
        value=True,
        help="تفعيل إرسال إشعار فوري عند استلام طلب جديد."
    )
    notify_confirmed = st.checkbox(
        "إشعارات الطلبات المكتملة (Order Confirmed)",
        value=True,
        help="تفعيل إرسال إشعار عند اكتمال الطلب وتأكيد الأرباح."
    )

    # تخصيص مظهر تنبيهات ديسكورد (اسم البوت، صورته، ألوان التنبيه)
    with st.expander("🎨 تخصيص مظهر إشعارات ديسكورد"):
        bot_username = st.text_input(
            "اسم البوت (Bot Username)",
            value="Eldorado Seller Notifier",
            help="الاسم الذي يظهر كمرسل للرسائل في ديسكورد"
        )
        bot_avatar_url = st.text_input(
            "رابط صورة البوت (Avatar URL)",
            value="https://cdn-icons-png.flaticon.com/512/888/888879.png",
            help="رابط أيقونة البوت التي ستظهر في ديسكورد (اختياري)"
        )
        new_order_color_hex = st.color_picker(
            "لون تنبيه الطلب الجديد",
            value="#FFA500",
            help="اللون الجانبي لبطاقة ديسكورد عند وصول طلب جديد"
        )
        confirmed_color_hex = st.color_picker(
            "لون تنبيه الطلب المكتمل",
            value="#2ECC71",
            help="اللون الجانبي لبطاقة ديسكورد عند اكتمال الطلب"
        )

    st.divider()

    # التحديث التلقائي للوحة التحكم
    st.subheader("🔄 التحديث التلقائي (Auto-Refresh)")
    auto_refresh_enabled = st.checkbox(
        "تفعيل التحديث التلقائي",
        value=False,
        help="يقوم بتحديث شاشة البيانات بشكل دوري تلقائياً"
    )
    refresh_seconds = st.slider(
        "فاصل التحديث (بالثواني)",
        min_value=10,
        max_value=120,
        value=30,
        step=5,
        help="عدد الثواني بين كل عملية تحديث تلقائي للبيانات"
    )


# ---------------------------------------------------------
# دالة مساعدة لتحويل Hex Color إلى Decimal لديسكورد
# ---------------------------------------------------------
def hex_to_int(hex_code: str) -> int:
    """تحويل كود اللون السداسي عشري إلى رقم صحيح لـ Discord Embed"""
    try:
        return int(hex_code.lstrip("#"), 16)
    except Exception:
        return 16753920


# ---------------------------------------------------------
# 3. نظام إشعارات ديسكورد (Discord Alert Function)
# ---------------------------------------------------------
def send_discord_alert(event_type: str, order_data: dict):
    """
    إرسال إشعار فوري إلى قناة ديسكورد عبر Webhook مع دعم التخصيص الكامل
    :param event_type: نوع الإشعار ('new_order' أو 'confirmed')
    :param order_data: قاموس يحتوي على تفاصيل الطلب
    :return: tuple (bool: النجاح، str: رسالة الحالة)
    """
    # التحقق من وجود رابط Webhook، وإذا لم يوجد تتوقف الدالة
    if not discord_webhook_url or not discord_webhook_url.strip():
        return False, "رابط Discord Webhook غير متوفر. يرجى إدخاله في القائمة الجانبية."

    # تجهيز كود الـ Mention باستخدام <@ID> إذا قام المستخدم بإدخال Discord ID
    mention_str = f"<@{discord_user_id.strip()}> " if (discord_user_id and discord_user_id.strip()) else ""

    # إعداد الحقول المخصصة للمظهر (اسم البوت وصورته)
    current_bot_name = bot_username.strip() if (bot_username and bot_username.strip()) else "Eldorado Seller Notifier"
    payload = {
        "username": current_bot_name
    }
    if bot_avatar_url and bot_avatar_url.strip():
        payload["avatar_url"] = bot_avatar_url.strip()

    # معالجة حدث "طلب جديد"
    if event_type == "new_order":
        if not notify_new_order:
            return False, "إشعارات الطلبات الجديدة غير مفعّلة في الإعدادات."
        
        order_id = order_data.get("رقم الطلب", "غير محدد")
        game_name = order_data.get("اللعبة/المنتج", "غير محدد")
        price = order_data.get("السعر ($)", 0.0)

        # محتوى الرسالة التي تتضمن المنشن، رقم الطلب، اسم اللعبة، والسعر
        content = f"{mention_str}🚨 **طلب جديد على إلدورادو!**"
        payload["content"] = content
        payload["embeds"] = [
            {
                "title": "📦 تفاصيل الطلب الجديد",
                "color": hex_to_int(new_order_color_hex),
                "fields": [
                    {"name": "رقم الطلب", "value": str(order_id), "inline": True},
                    {"name": "اللعبة / المنتج", "value": str(game_name), "inline": True},
                    {"name": "السعر ($)", "value": f"${price:,.2f}", "inline": True}
                ],
                "footer": {"text": f"{current_bot_name} • Eldorado Seller Dashboard"},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        ]

    # معالجة حدث "طلب مكتمل"
    elif event_type == "confirmed":
        if not notify_confirmed:
            return False, "إشعارات الطلبات المكتملة غير مفعّلة في الإعدادات."
        
        order_id = order_data.get("رقم الطلب", "غير محدد")
        profit = order_data.get("صافي الربح ($)", 0.0)

        # محتوى الرسالة التي تتضمن المنشن، رقم الطلب، وصافي الربح
        content = f"{mention_str}💰 **تم تأكيد واكتمال الطلب!**"
        payload["content"] = content
        payload["embeds"] = [
            {
                "title": "✅ تفاصيل الأرباح المؤكدة",
                "color": hex_to_int(confirmed_color_hex),
                "fields": [
                    {"name": "رقم الطلب", "value": str(order_id), "inline": True},
                    {"name": "صافي الربح ($)", "value": f"${profit:,.2f}", "inline": True}
                ],
                "footer": {"text": f"{current_bot_name} • Eldorado Seller Dashboard"},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        ]
    else:
        return False, f"نوع حدث غير معروف: {event_type}"

    # إرسال الطلب عبر requests.post بصيغة JSON
    try:
        response = requests.post(
            discord_webhook_url.strip(),
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code in [200, 204]:
            return True, "تم إرسال الإشعار إلى ديسكورد بنجاح!"
        else:
            return False, f"رد ديسكورد برمز خطأ: {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"حدث خطأ أثناء الاتصال بديسكورد: {str(e)}"


# ---------------------------------------------------------
# 4. نظام جلب البيانات (Data Fetching)
# ---------------------------------------------------------
def fetch_orders(api_key: str, mode: str = "بيانات تجريبية (Demo)", endpoint: str = "https://eldorado.gg/api/orders") -> tuple[pd.DataFrame, str]:
    """
    جلب بيانات المبيعات والطلبات الخاصة بالبائع
    إذا لم يتوفر مفتاح API أو كان الوضع تجريبياً يتم إرجاع بيانات وهمية (Mock Data)
    أما في حالة الاتصال الحي، يتم التواصل الفعلي مع الـ API ومعالجة الاستجابة
    :return: tuple (pd.DataFrame, message)
    """
    if mode == "بيانات تجريبية (Demo)" or not api_key or not api_key.strip():
        # =====================================================================
        # بيانات وهمية (Mock Data) مطابقة لهيكل بيانات إلدورادو
        # الأعمدة: (رقم الطلب، التاريخ، اللعبة/المنتج، الحالة، السعر ($)، صافي الربح ($))
        # =====================================================================
        mock_data = {
            "رقم الطلب": [
                "ELD-88201", "ELD-88202", "ELD-88203", "ELD-88204", "ELD-88205",
                "ELD-88206", "ELD-88207", "ELD-88208", "ELD-88209", "ELD-88210",
                "ELD-88211", "ELD-88212"
            ],
            "التاريخ": [
                "2026-10-10", "2026-10-11", "2026-10-11", "2026-10-12", "2026-10-13",
                "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-15", "2026-10-16",
                "2026-10-16", "2026-10-17"
            ],
            "اللعبة/المنتج": [
                "Fortnite V-Bucks", "Roblox Robux", "World of Warcraft Gold", "GTA V Modded Account",
                "Old School RuneScape Gold", "Valorant Points & Accounts", "Fortnite V-Bucks",
                "Roblox Robux", "Clash of Clans Gems", "World of Warcraft Gold",
                "GTA V Modded Account", "Valorant Points & Accounts"
            ],
            "الحالة": [
                "مكتمل", "مكتمل", "مكتمل", "مكتمل", "قيد المراجعة",
                "مكتمل", "مكتمل", "مكتمل", "قيد التنفيذ", "مكتمل",
                "مكتمل", "مكتمل"
            ],
            "السعر ($)": [
                45.00, 80.00, 150.00, 65.00, 35.00, 95.00,
                55.00, 120.00, 40.00, 210.00, 70.00, 115.00
            ],
            "صافي الربح ($)": [
                38.25, 68.00, 127.50, 55.25, 29.75, 80.75,
                46.75, 102.00, 34.00, 178.50, 59.50, 97.75
            ]
        }
        return pd.DataFrame(mock_data), "تم تحميل البيانات التجريبية بنجاح."

    # =========================================================================
    # [الاتصال الحي الحقيقي بـ API إلدورادو]
    # Real Eldorado API Live Connection
    # =========================================================================
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "User-Agent": "EldoradoSellerDashboard/1.0"
    }
    
    target_url = endpoint.strip() if endpoint and endpoint.strip() else "https://eldorado.gg/api/orders"
    
    try:
        response = requests.get(target_url, headers=headers, timeout=12)
        if response.status_code == 200:
            json_data = response.json()
            # التعامل مع أشكال الاستجابات المحتملة من الـ API (قائمة مباشرة أو قاموس يحتوي على مفتاح)
            items = []
            if isinstance(json_data, list):
                items = json_data
            elif isinstance(json_data, dict):
                items = json_data.get("orders") or json_data.get("items") or json_data.get("data") or []
            
            if items:
                formatted_orders = []
                for item in items:
                    formatted_orders.append({
                        "رقم الطلب": str(item.get("orderId") or item.get("id") or item.get("orderNumber") or "غير محدد"),
                        "التاريخ": str(item.get("createdAt") or item.get("date") or datetime.date.today().isoformat())[:10],
                        "اللعبة/المنتج": str(item.get("title") or item.get("offerTitle") or item.get("gameName") or "منتج إلدورادو"),
                        "الحالة": str(item.get("status") or item.get("orderStatus") or "مكتمل"),
                        "السعر ($)": float(item.get("totalPrice") or item.get("price") or item.get("amount") or 0.0),
                        "صافي الربح ($)": float(item.get("sellerProfit") or item.get("profit") or item.get("netProfit") or 0.0)
                    })
                return pd.DataFrame(formatted_orders), f"تم جلب {len(formatted_orders)} طلب حقيقي من API إلدورادو بنجاح."
            else:
                empty_df = pd.DataFrame(columns=["رقم الطلب", "التاريخ", "اللعبة/المنتج", "الحالة", "السعر ($)", "صافي الربح ($)"])
                return empty_df, "تم الاتصال بنجاح ولكن لا توجد أي طلبات مسجلة في هذا الحساب حالياً."
        elif response.status_code == 401:
            return pd.DataFrame(), "خطأ 401: مفتاح API أو Bearer Token غير صالح أو انتهت صلاحيته."
        elif response.status_code == 403:
            return pd.DataFrame(), "خطأ 403: ليس لديك الصلاحية الكافية للوصول إلى نقطة النهاية هذه."
        elif response.status_code == 404:
            return pd.DataFrame(), f"خطأ 404: نقطة النهاية ({target_url}) غير موجودة."
        else:
            return pd.DataFrame(), f"استجابة غير متوقعة من إلدورادو: كود {response.status_code} - {response.text[:150]}"
    except requests.exceptions.RequestException as ex:
        return pd.DataFrame(), f"خطأ في الاتصال بالشبكة مع إلدورادو: {str(ex)}"


# ---------------------------------------------------------
# 5. واجهة العرض الرئيسية والتحليلات والفلاتر
# ---------------------------------------------------------
# إدارة حالة العرض التجريبي في st.session_state
if "show_demo_data" not in st.session_state:
    st.session_state.show_demo_data = False

# شريط التحكم العلوي
col_header1, col_header2, col_header3 = st.columns([3, 1, 1])
with col_header1:
    st.write("مرحباً بك في لوحة تحكم مبيعات وأرباح إلدورادو. يمكنك مراقبة الطلبات والأداء المالي بسهولة.")
with col_header2:
    if st.button("📊 عرض ببيانات تجريبية", use_container_width=True):
        st.session_state.show_demo_data = True
with col_header3:
    if st.button("🔄 تحديث يدوي الآن", use_container_width=True):
        st.rerun()

# التحقق من شرط العرض: إذا تم إدخال مفتاح API أو اختيار وضع الاتصال أو تم الضغط على زر "عرض ببيانات تجريبية"
should_display = bool(eldorado_api_key and eldorado_api_key.strip()) or st.session_state.show_demo_data or (data_source_mode == "بيانات تجريبية (Demo)")

# إعداد الـ Fragment للتحديث التلقائي
fragment_interval = f"{refresh_seconds}s" if auto_refresh_enabled else None

@st.fragment(run_every=fragment_interval)
def render_dashboard_fragment():
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if auto_refresh_enabled:
        st.caption(f"🟢 **التحديث التلقائي نشط** (كل {refresh_seconds} ثانية) | آخر تحديث: `{current_time_str}`")
    else:
        st.caption(f"⚪ التحديث التلقائي غير مفعل | آخر قراءة: `{current_time_str}`")

    if not should_display:
        st.info("ℹ️ لعرض المؤشرات والبيانات، يرجى إدخال Eldorado API Key في القائمة الجانبية أو الضغط على زر **'عرض ببيانات تجريبية'** بالأعلى.")
        return

    # جلب البيانات
    df, status_msg = fetch_orders(
        api_key=eldorado_api_key,
        mode=data_source_mode,
        endpoint=eldorado_api_endpoint
    )

    # عرض حالة جلب البيانات
    if df.empty and status_msg:
        st.error(status_msg)
        st.info("💡 يمكنك العودة لاختيار **'بيانات تجريبية (Demo)'** من القائمة الجانبية لمعاينة اللوحة.")
        return
    elif status_msg:
        st.toast(status_msg)

    # =====================================================
    # الفلاتر المتقدمة لتصفية البيانات (Advanced Filters)
    # =====================================================
    with st.expander("🔍 فلاتر متقدمة لتصفية الطلبات والبيانات", expanded=False):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            search_query = st.text_input(
                "🔎 بحث برقم الطلب أو اسم اللعبة/المنتج:",
                placeholder="اكتب رقم الطلب أو اسم اللعبة..."
            )
        with col_f2:
            unique_statuses = sorted(list(df["الحالة"].dropna().unique()))
            selected_statuses = st.multiselect(
                "📌 تصفية حسب حالة الطلب:",
                options=unique_statuses,
                default=unique_statuses
            )

        col_f3, col_f4 = st.columns(2)
        with col_f3:
            unique_games = sorted(list(df["اللعبة/المنتج"].dropna().unique()))
            selected_games = st.multiselect(
                "🎮 تصفية حسب اللعبة / المنتج:",
                options=unique_games,
                default=unique_games
            )
        with col_f4:
            min_price = float(df["السعر ($)"].min()) if not df.empty else 0.0
            max_price = float(df["السعر ($)"].max()) if not df.empty else 100.0
            if min_price == max_price:
                max_price += 10.0
            price_range = st.slider(
                "💵 نطاق السعر ($):",
                min_value=min_price,
                max_value=max_price,
                value=(min_price, max_price),
                step=1.0
            )

    # تطبيق الفلاتر برمجياً
    filtered_df = df.copy()

    # 1. تصفية بالبحث النصي
    if search_query and search_query.strip():
        q = search_query.strip().lower()
        filtered_df = filtered_df[
            filtered_df["رقم الطلب"].astype(str).str.lower().str.contains(q, na=False) |
            filtered_df["اللعبة/المنتج"].astype(str).str.lower().str.contains(q, na=False)
        ]

    # 2. تصفية بحالة الطلب
    if selected_statuses:
        filtered_df = filtered_df[filtered_df["الحالة"].isin(selected_statuses)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    # 3. تصفية بالألعاب/المنتجات
    if selected_games:
        filtered_df = filtered_df[filtered_df["اللعبة/المنتج"].isin(selected_games)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    # 4. تصفية بنطاق السعر
    filtered_df = filtered_df[
        (filtered_df["السعر ($)"] >= price_range[0]) &
        (filtered_df["السعر ($)"] <= price_range[1])
    ]

    # =====================================================
    # عرض النتائج والإحصائيات
    # =====================================================
    if filtered_df.empty:
        st.warning("⚠️ لا توجد طلبات مطابقة للمعايير المحددة في الفلاتر. جرب تعديل خيارات التصفية.")
    else:
        # حساب الإحصائيات برمجياً من الـ DataFrame المفلتر
        total_sales = filtered_df["السعر ($)"].sum()
        total_profit = filtered_df["صافي الربح ($)"].sum()
        total_orders = len(filtered_df)

        st.markdown("### 📌 ملخص الإحصائيات (Metrics)")
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        with metric_col1:
            st.metric(
                label="💵 إجمالي المبيعات",
                value=f"${total_sales:,.2f}"
            )
        with metric_col2:
            st.metric(
                label="📈 صافي الأرباح",
                value=f"${total_profit:,.2f}"
            )
        with metric_col3:
            st.metric(
                label="🛒 عدد الطلبات",
                value=f"{total_orders}"
            )

        st.divider()

        # جدول البيانات بالكامل مع تفعيل use_container_width
        st.markdown(f"### 📋 جدول الطلبات والمبيعات ({len(filtered_df)} من أصل {len(df)})")
        st.dataframe(filtered_df, use_container_width=True)

        st.divider()

        # رسم بياني شريطي لصافي الأرباح حسب اللعبة
        st.markdown("### 📊 صافي الربح حسب اللعبة / المنتج")
        profit_by_game = filtered_df.groupby("اللعبة/المنتج")["صافي الربح ($)"].sum()
        st.bar_chart(profit_by_game)


# استدعاء دالة عرض لوحة التحكم
render_dashboard_fragment()


# ---------------------------------------------------------
# 6. قسم اختبار الديسكورد (Testing Section)
# ---------------------------------------------------------
st.divider()
st.subheader("🧪 قسم اختبار الديسكورد")
st.write("استخدم الأزرار التالية لإرسال إشعارات تجريبية إلى قناة ديسكورد بالاسم والصورة والألوان المخصصة:")

test_col1, test_col2 = st.columns(2)

with test_col1:
    if st.button("إرسال رسالة: طلب جديد", use_container_width=True):
        # تجهيز بيانات وهمية لطلب جديد
        sample_new_order = {
            "رقم الطلب": "ELD-TEST-501",
            "اللعبة/المنتج": "Fortnite V-Bucks (5,000 Pack)",
            "السعر ($)": 32.50
        }
        success, msg = send_discord_alert("new_order", sample_new_order)
        # إظهار رسالة نجاح st.success عند الضغط
        st.success("تم الضغط على زر 'إرسال رسالة: طلب جديد' بنجاح!")
        if success:
            st.info(f"حالة ديسكورد: {msg}")
        else:
            st.warning(f"ملاحظة ديسكورد: {msg}")

with test_col2:
    if st.button("إرسال رسالة: طلب مكتمل", use_container_width=True):
        # تجهيز بيانات وهمية لطلب مكتمل بأرباح صافية
        sample_confirmed_order = {
            "رقم الطلب": "ELD-TEST-501",
            "صافي الربح ($)": 27.60
        }
        success, msg = send_discord_alert("confirmed", sample_confirmed_order)
        # إظهار رسالة نجاح st.success عند الضغط
        st.success("تم الضغط على زر 'إرسال رسالة: طلب مكتمل' بنجاح!")
        if success:
            st.info(f"حالة ديسكورد: {msg}")
        else:
            st.warning(f"ملاحظة ديسكورد: {msg}")

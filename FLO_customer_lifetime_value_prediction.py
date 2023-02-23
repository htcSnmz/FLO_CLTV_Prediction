"""
BG-NBD ve Gamma-Gamma ile CLTV Tahmini
CLTV Prediction with BG-NBD and Gamma-Gamma
-------------------------------------------
İş Problemi:
FLO satış ve pazarlama faaliyetleri için roadmap
belirlemek istemektedir. Şirketin orta uzun vadeli plan
yapabilmesi için var olan müşterilerin gelecekte şirkete
sağlayacakları potansiyel değerin tahmin edilmesi
gerekmektedir.

Veri Seti Hikayesi:
Veri seti Flo’dan son alışverişlerini 2020 - 2021 yıllarında OmniChannel (hem online hem offline alışveriş yapan)
olarak yapan müşterilerin geçmiş alışveriş davranışlarından elde edilen bilgilerden oluşmaktadır.

Değişkenler:
13 Değişken 19.945 Gözlem 2.7MB
master_id Eşsiz müşteri numarası
order_channel Alışveriş yapılan platforma ait hangi kanalın kullanıldığı (Android, ios, Desktop, Mobile)
last_order_channel En son alışverişin yapıldığı kanal
first_order_date Müşterinin yaptığı ilk alışveriş tarihi
last_order_date Müşterinin yaptığı son alışveriş tarihi
last_order_date_online Müşterinin online platformda yaptığı son alışveriş tarihi
last_order_date_offline Müşterinin offline platformda yaptığı son alışveriş tarihi
order_num_total_ever_online Müşterinin online platformda yaptığı toplam alışveriş sayısı
order_num_total_ever_offline Müşterinin offline'da yaptığı toplam alışveriş sayısı
customer_value_total_ever_offline Müşterinin offline alışverişlerinde ödediği toplam ücret
customer_value_total_ever_online Müşterinin online alışverişlerinde ödediği toplam ücret
interested_in_categories_12 Müşterinin son 12 ayda alışveriş yaptığı kategorilerin listesi
"""

# Görev 1: Veriyi Hazırlama
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt
from lifetimes import BetaGeoFitter
from lifetimes import GammaGammaFitter
from lifetimes.plotting import plot_period_transactions
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 500)
pd.set_option("display.float_format", lambda x: "%.4f" % x)

# Adım 1: flo_data_20K.csv verisini okuyunuz.
df_ = pd.read_csv("CLTV_Prediction/flo_data_20k.csv")
df = df_.copy()
df.info()
df.describe().T
df.head()

# Adım 2: Aykırı değerleri baskılamak için gerekli olan outlier_thresholds ve replace_with_thresholds fonksiyonlarını tanımlayınız.
# Not: cltv hesaplanırken frequency değerleri integer olması gerekmektedir.Bu nedenle alt ve üst limitlerini round() ile yuvarlayınız.
def outlier_threshold(dataframe, variable):
    q1 = dataframe[variable].quantile(0.01)
    q3 = dataframe[variable].quantile(0.99)
    iqr = q3 - q1
    up_limit = q3 + 1.5 * iqr
    low_limit = q1 - 1.5 * iqr
    return low_limit, up_limit

def replace_with_thresholds(dataframe, variable):
    low_limit, up_limit = outlier_threshold(dataframe, variable)
    dataframe.loc[dataframe[variable] > up_limit, variable] = round(up_limit, 0)
    dataframe.loc[dataframe[variable] < low_limit, variable] = round(low_limit,0)

# Adım3: "order_num_total_ever_online", "order_num_total_ever_offline", "customer_value_total_ever_offline",
# "customer_value_total_ever_online" değişkenlerinin aykırı değerleri varsa baskılayanız.
cols = ["order_num_total_ever_online", "order_num_total_ever_offline", "customer_value_total_ever_offline", "customer_value_total_ever_online"]
for col in cols:
    replace_with_thresholds(df, col)

# Adım4: Omnichannel müşterilerin hem online'dan hem de offline platformlardan alışveriş yaptığını ifade etmektedir. Her bir müşterinin toplam
# alışveriş sayısı ve harcaması için yeni değişkenler oluşturunuz.
df["order_num_total"] = df["order_num_total_ever_offline"] + df["order_num_total_ever_online"]
df["customer_value_total"] = df["customer_value_total_ever_offline"] + df["customer_value_total_ever_online"]

# Adım 5: Değişken tiplerini inceleyiniz. Tarih ifade eden değişkenlerin tipini date'e çeviriniz.
date_cols = [col for col in df.columns if "date" in col]
df[date_cols] = df[date_cols].apply(pd.to_datetime)
df.info()

# Görev 2: CLTV Veri Yapısının Oluşturulması
# Adım 1: Veri setindeki en son alışverişin yapıldığı tarihten 2 gün sonrasını analiz tarihi olarak alınız.
# Adım 2: customer_id, recency_cltv_weekly, T_weekly, frequency ve monetary_cltv_avg değerlerinin yer aldığı yeni bir cltv dataframe'i oluşturunuz.
# Monetary değeri satın alma başına ortalama değer olarak, recency ve tenure değerleri ise haftalık cinsten ifade edilecek.
analysis_date = df["last_order_date"].max() + dt.timedelta(days=2)
cltv_df = pd.DataFrame()
cltv_df["customer_id"] = df["master_id"]
cltv_df["recency_cltv_weekly"] = ((df["last_order_date"] - df["first_order_date"]).astype("timedelta64[D]")) / 7
cltv_df["T_weekly"] = ((analysis_date - df["first_order_date"]).astype("timedelta64[D]")) / 7
cltv_df["frequency"] = df["order_num_total"]
cltv_df["monetary_cltv_avg"] = df["customer_value_total"] / df["order_num_total"]
cltv_df = cltv_df[cltv_df["frequency"] > 1]
cltv_df.head()

# Görev 3: BG/NBD, Gamma-Gamma Modellerinin Kurulması ve CLTV’nin Hesaplanması
# Adım1: BG/NBD modelini fit ediniz.
# 3 ay içerisinde müşterilerden beklenen satın almaları tahmin ediniz ve exp_sales_3_month olarak cltv dataframe'ine ekleyiniz.
# 6 ay içerisinde müşterilerden beklenen satın almaları tahmin ediniz ve exp_sales_6_month olarak cltv dataframe'ine ekleyiniz.
bgf = BetaGeoFitter(penalizer_coef=0.001)
bgf.fit(cltv_df["frequency"], cltv_df["recency_cltv_weekly"], cltv_df["T_weekly"])
cltv_df["exp_sales_3_month"] = bgf.predict(12, cltv_df["frequency"], cltv_df["recency_cltv_weekly"], cltv_df["T_weekly"])
cltv_df["exp_sales_6_month"] = bgf.predict(24, cltv_df["frequency"], cltv_df["recency_cltv_weekly"], cltv_df["T_weekly"])

# Adım2: Gamma-Gamma modelini fit ediniz. Müşterilerin ortalama bırakacakları değeri tahminleyip exp_average_value olarak cltv
# dataframe'ine ekleyiniz.
ggf = GammaGammaFitter(penalizer_coef=0.01)
ggf.fit(cltv_df["frequency"], cltv_df["monetary_cltv_avg"])
cltv_df["exp_average_value"] = ggf.conditional_expected_average_profit(cltv_df["frequency"], cltv_df["monetary_cltv_avg"])

# Adım3: 6 aylık CLTV hesaplayınız ve cltv ismiyle dataframe'e ekleyiniz.
# Cltv değeri en yüksek 20 kişiyi gözlemleyiniz.
cltv_df["cltv"] = ggf.customer_lifetime_value(bgf,
                                              cltv_df["frequency"],
                                              cltv_df["recency_cltv_weekly"],
                                              cltv_df["T_weekly"],
                                              cltv_df["monetary_cltv_avg"],
                                              time=6,
                                              discount_rate=0.01,
                                              freq="W")

# Görev 4: CLTV Değerine Göre Segmentlerin Oluşturulması
# Adım1: 6 aylık CLTV'ye göre tüm müşterilerinizi 4 gruba (segmente) ayırınız ve grup isimlerini veri setine ekleyiniz.
cltv_df["segment"] = pd.qcut(cltv_df["cltv"], 4, labels=["D", "C", "B", "A"])
cltv_df.groupby("segment").agg(["mean", "sum", "count"])
cltv_df.head(20)
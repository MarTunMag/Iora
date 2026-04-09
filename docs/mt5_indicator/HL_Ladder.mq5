//+------------------------------------------------------------------+
//|                                                   HL_Ladder.mq5    |
//|                          Copyright 2025, Marius Magnusson        |
//|                           matu.magnussons@gmail.com              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, Marius Magnusson"
#property link      "matu.magnussons@gmail.com"
#property version   "12.00" // Definitive Final Version - Simplified Core Logic
#property indicator_chart_window

#property indicator_buffers 14
#property indicator_plots   0

//--- Constants
#define MAX_HISTORY 3

//--- Data Structures
struct PivotPoint { double price; datetime time; };

//--- User Inputs
input int    LineWidth=2;
input ENUM_LINE_STYLE BrokenLineStyle=STYLE_DOT;
input int    LabelFontSize=8;
input int    Label_Y_Offset_Pts=5;
input bool L1_Enable=true; input int L1_L=5; input int L1_R=1; input color L1_H_Color=clrDarkOrange; input color L1_L_Color=clrDarkOrange;
input bool L2_Enable=true; input int L2_L=15; input int L2_R=1; input color L2_H_Color=clrChocolate; input color L2_L_Color=clrChocolate;
input bool L3_Enable=true; input int L3_L=60; input int L3_R=1; input color L3_H_Color=clrRed; input color L3_L_Color=clrBlue;
input bool L4_Enable=true; input int L4_L=240; input int L4_R=1; input color L4_H_Color=clrDarkRed; input color L4_L_Color=clrDarkBlue;
input bool L5_Enable=true; input int L5_L=1440; input int L5_R=1; input color L5_H_Color=clrMagenta; input color L5_L_Color=clrPurple;
input bool L6_Enable=true; input int L6_L=10080; input int L6_R=1; input color L6_H_Color=clrGray; input color L6_L_Color=clrGray;
input bool L7_Enable=true; input int L7_L=43200; input int L7_R=1; input color L7_H_Color=clrWhite; input color L7_L_Color=clrWhite;

//--- GLOBAL ARRAYS FOR CONFIGURATION AND STATE ---
bool     g_IsEnabled[7];
int      g_L_Value[7], g_R_Value[7];
color    g_HighColor[7], g_LowColor[7];
string   g_Label[7];
PivotPoint g_LatestHigh[7], g_LatestLow[7];
double   g_ConfirmedHighPrice[7], g_ConfirmedLowPrice[7];

//--- DEFINITIVELY CORRECTED, FLATTENED HISTORY ARRAYS ---
double   g_history_price[7][2][MAX_HISTORY]; // [level][0=low, 1=high][idx]
datetime g_history_time[7][2][MAX_HISTORY];

//--- Global Buffers
double L1_HighBuffer[], L1_LowBuffer[], L2_HighBuffer[], L2_LowBuffer[], L3_HighBuffer[], L3_LowBuffer[],
       L4_HighBuffer[], L4_LowBuffer[], L5_HighBuffer[], L5_LowBuffer[], L6_HighBuffer[], L6_LowBuffer[],
       L7_HighBuffer[], L7_LowBuffer[];

//--- Function Prototypes
void FindPivots(int level_idx, const double &m1_high[], const double &m1_low[], const datetime &m1_time[], int total_bars);
void AddToHistory(int level_idx, bool isHigh, const PivotPoint &new_pivot);
void DrawHistory(const double &high[], const double &low[]);

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   IndicatorSetString(INDICATOR_SHORTNAME,"HL Ladder");
   SetIndexBuffer(0,L1_HighBuffer,INDICATOR_DATA); PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,0); SetIndexBuffer(1,L1_LowBuffer,INDICATOR_DATA); PlotIndexSetDouble(1,PLOT_EMPTY_VALUE,0);
   SetIndexBuffer(2,L2_HighBuffer,INDICATOR_DATA); PlotIndexSetDouble(2,PLOT_EMPTY_VALUE,0); SetIndexBuffer(3,L2_LowBuffer,INDICATOR_DATA); PlotIndexSetDouble(3,PLOT_EMPTY_VALUE,0);
   SetIndexBuffer(4,L3_HighBuffer,INDICATOR_DATA); PlotIndexSetDouble(4,PLOT_EMPTY_VALUE,0); SetIndexBuffer(5,L3_LowBuffer,INDICATOR_DATA); PlotIndexSetDouble(5,PLOT_EMPTY_VALUE,0);
   SetIndexBuffer(6,L4_HighBuffer,INDICATOR_DATA); PlotIndexSetDouble(6,PLOT_EMPTY_VALUE,0); SetIndexBuffer(7,L4_LowBuffer,INDICATOR_DATA); PlotIndexSetDouble(7,PLOT_EMPTY_VALUE,0);
   SetIndexBuffer(8,L5_HighBuffer,INDICATOR_DATA); PlotIndexSetDouble(8,PLOT_EMPTY_VALUE,0); SetIndexBuffer(9,L5_LowBuffer,INDICATOR_DATA); PlotIndexSetDouble(9,PLOT_EMPTY_VALUE,0);
   SetIndexBuffer(10,L6_HighBuffer,INDICATOR_DATA); PlotIndexSetDouble(10,PLOT_EMPTY_VALUE,0); SetIndexBuffer(11,L6_LowBuffer,INDICATOR_DATA); PlotIndexSetDouble(11,PLOT_EMPTY_VALUE,0);
   SetIndexBuffer(12,L7_HighBuffer,INDICATOR_DATA); PlotIndexSetDouble(12,PLOT_EMPTY_VALUE,0); SetIndexBuffer(13,L7_LowBuffer,INDICATOR_DATA); PlotIndexSetDouble(13,PLOT_EMPTY_VALUE,0);
   
   g_IsEnabled[0]=L1_Enable; g_L_Value[0]=L1_L; g_R_Value[0]=L1_R; g_HighColor[0]=L1_H_Color; g_LowColor[0]=L1_L_Color; g_Label[0]="L"+(string)L1_L;
   g_IsEnabled[1]=L2_Enable; g_L_Value[1]=L2_L; g_R_Value[1]=L2_R; g_HighColor[1]=L2_H_Color; g_LowColor[1]=L2_L_Color; g_Label[1]="L"+(string)L2_L;
   g_IsEnabled[2]=L3_Enable; g_L_Value[2]=L3_L; g_R_Value[2]=L3_R; g_HighColor[2]=L3_H_Color; g_LowColor[2]=L3_L_Color; g_Label[2]="L"+(string)L3_L;
   g_IsEnabled[3]=L4_Enable; g_L_Value[3]=L4_L; g_R_Value[3]=L4_R; g_HighColor[3]=L4_H_Color; g_LowColor[3]=L4_L_Color; g_Label[3]="L"+(string)L4_L;
   g_IsEnabled[4]=L5_Enable; g_L_Value[4]=L5_L; g_R_Value[4]=L5_R; g_HighColor[4]=L5_H_Color; g_LowColor[4]=L5_L_Color; g_Label[4]="L"+(string)L5_L;
   g_IsEnabled[5]=L6_Enable; g_L_Value[5]=L6_L; g_R_Value[5]=L6_R; g_HighColor[5]=L6_H_Color; g_LowColor[5]=L6_L_Color; g_Label[5]="L"+(string)L6_L;
   g_IsEnabled[6]=L7_Enable; g_L_Value[6]=L7_L; g_R_Value[6]=L7_R; g_HighColor[6]=L7_H_Color; g_LowColor[6]=L7_L_Color; g_Label[6]="L"+(string)L7_L;
   
   ArrayInitialize(g_history_price,0);
   ArrayInitialize(g_history_time,0);
   ArrayInitialize(g_ConfirmedHighPrice,0);
   ArrayInitialize(g_ConfirmedLowPrice,0);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason){ ObjectsDeleteAll(0,"HL_"); }

//+------------------------------------------------------------------+
//| Main Calculation                                                 |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[], const double &open[], const double &high[], const double &low[], const double &close[], const long &tick_volume[], const long &volume[], const int &spread[])
  {
   const int M1_BARS_TO_REQUEST = g_L_Value[6] + 250; 
   double m1_high[]; double m1_low[]; datetime m1_time[];
   ArraySetAsSeries(m1_high,true); ArraySetAsSeries(m1_low,true); ArraySetAsSeries(m1_time,true);
   
   int m1_bars_copied = CopyHigh(_Symbol,PERIOD_M1,0,M1_BARS_TO_REQUEST,m1_high);
   if(m1_bars_copied <= 0) return(0);
   if(CopyLow(_Symbol,PERIOD_M1,0,M1_BARS_TO_REQUEST,m1_low) != m1_bars_copied || CopyTime(_Symbol,PERIOD_M1,0,M1_BARS_TO_REQUEST,m1_time) != m1_bars_copied) return(0);

   for(int i=0; i<7; i++){ FindPivots(i, m1_high,m1_low,m1_time,m1_bars_copied); }

   for(int i=6; i>=1; i--)
     {
      if(!g_IsEnabled[i]) continue;
      if(g_LatestHigh[i].price > 0 && g_LatestLow[i-1].time > g_LatestHigh[i].time)
        {
         if(g_LatestHigh[i].time != g_history_time[i][1][0])
           { AddToHistory(i, true, g_LatestHigh[i]); g_ConfirmedHighPrice[i] = g_LatestHigh[i].price; }
        }
      if(g_LatestLow[i].price > 0 && g_LatestHigh[i-1].time > g_LatestLow[i].time)
        {
         if(g_LatestLow[i].time != g_history_time[i][0][0])
           { AddToHistory(i, false, g_LatestLow[i]); g_ConfirmedLowPrice[i] = g_LatestLow[i].price; }
        }
     }
   
   DrawHistory(high, low);
     
   int start_bar = prev_calculated > 0 ? prev_calculated - 1 : 0;
   for(int i=start_bar; i<rates_total; i++)
     {
      L1_HighBuffer[i]=g_ConfirmedHighPrice[0]; L1_LowBuffer[i]=g_ConfirmedLowPrice[0]; L2_HighBuffer[i]=g_ConfirmedHighPrice[1]; L2_LowBuffer[i]=g_ConfirmedLowPrice[1];
      L3_HighBuffer[i]=g_ConfirmedHighPrice[2]; L3_LowBuffer[i]=g_ConfirmedLowPrice[2]; L4_HighBuffer[i]=g_ConfirmedHighPrice[3]; L4_LowBuffer[i]=g_ConfirmedLowPrice[3];
      L5_HighBuffer[i]=g_ConfirmedHighPrice[4]; L5_LowBuffer[i]=g_ConfirmedLowPrice[4]; L6_HighBuffer[i]=g_ConfirmedHighPrice[5]; L6_LowBuffer[i]=g_ConfirmedLowPrice[5];
      L7_HighBuffer[i]=g_ConfirmedHighPrice[6]; L7_LowBuffer[i]=g_ConfirmedLowPrice[6];
     }
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| Simplified Functions (No Classes)                                |
//+------------------------------------------------------------------+
void FindPivots(int level_idx, const double &m1_high[], const double &m1_low[], const datetime &m1_time[], int total_bars)
  {
   g_LatestHigh[level_idx].price=0; g_LatestLow[level_idx].price=0;
   if(!g_IsEnabled[level_idx] || total_bars<g_L_Value[level_idx]+g_R_Value[level_idx]+1) return;
   int L = g_L_Value[level_idx]; int R = g_R_Value[level_idx];
   for(int i=R; i<total_bars-L; i++)
     {
      if(g_LatestHigh[level_idx].price==0){bool isPivot=true; for(int j=1; j<=L; j++){if(m1_high[i+j]>=m1_high[i]){isPivot=false; break;}} if(isPivot){for(int j=1; j<=R; j++){if(m1_high[i-j]>m1_high[i]){isPivot=false; break;}}} if(isPivot){g_LatestHigh[level_idx].price=m1_high[i]; g_LatestHigh[level_idx].time=m1_time[i];}}
      if(g_LatestLow[level_idx].price==0){bool isPivot=true; for(int j=1; j<=L; j++){if(m1_low[i+j]<=m1_low[i]){isPivot=false; break;}} if(isPivot){for(int j=1; j<=R; j++){if(m1_low[i-j]<m1_low[i]){isPivot=false; break;}}} if(isPivot){g_LatestLow[level_idx].price=m1_low[i]; g_LatestLow[level_idx].time=m1_time[i];}}
      if(g_LatestHigh[level_idx].price!=0 && g_LatestLow[level_idx].price!=0)break;
     }
  }

void AddToHistory(int level_idx, bool isHigh, const PivotPoint &new_pivot)
  {
   int side_idx = isHigh ? 1 : 0;
   for(int i = MAX_HISTORY - 1; i > 0; i--) 
     {
      g_history_price[level_idx][side_idx][i] = g_history_price[level_idx][side_idx][i-1];
      g_history_time[level_idx][side_idx][i] = g_history_time[level_idx][side_idx][i-1];
     }
   g_history_price[level_idx][side_idx][0] = new_pivot.price;
   g_history_time[level_idx][side_idx][0] = new_pivot.time;
  }

void DrawHistory(const double &high[], const double &low[])
  {
   ObjectsDeleteAll(0, "HL_");
   for(int i=6; i>=1; i--)
     {
      if(!g_IsEnabled[i]) continue;
      
      // Draw Highs
      for(int h=0; h<MAX_HISTORY; h++)
        {
         if(g_history_time[i][1][h]==0) continue;
         bool is_broken = high[0] > g_history_price[i][1][h];
         ENUM_LINE_STYLE style = (h==0 && !is_broken) ? STYLE_SOLID : BrokenLineStyle;
         
         datetime pivot_time = g_history_time[i][1][h];
         double pivot_price = g_history_price[i][1][h];
         string label_text = g_Label[i]+" H";
         string base_name = "HL_"+g_Label[i]+"_H_"+(string)pivot_time;
         
         string line_name= base_name+"_line";
         datetime time2=pivot_time+PeriodSeconds(_Period);
         ObjectCreate(0,line_name,OBJ_TREND,0,pivot_time,pivot_price,time2,pivot_price);
         ObjectSetInteger(0,line_name,OBJPROP_COLOR,g_HighColor[i]);
         ObjectSetInteger(0,line_name,OBJPROP_WIDTH,LineWidth);
         ObjectSetInteger(0,line_name,OBJPROP_RAY_RIGHT,true);
         ObjectSetInteger(0,line_name,OBJPROP_STYLE,style);
         
         string label_name= base_name+"_label";
         double p_offset=Label_Y_Offset_Pts*_Point;
         ObjectCreate(0,label_name,OBJ_TEXT,0,pivot_time,pivot_price+p_offset);
         ObjectSetString(0,label_name,OBJPROP_TEXT,label_text);
         ObjectSetInteger(0,label_name,OBJPROP_COLOR,g_HighColor[i]);
         ObjectSetInteger(0,label_name,OBJPROP_FONTSIZE,LabelFontSize);
         ObjectSetInteger(0,label_name,OBJPROP_ANCHOR,ANCHOR_LEFT_LOWER);
        }
      
      // Draw Lows
      for(int l=0; l<MAX_HISTORY; l++)
        {
         if(g_history_time[i][0][l]==0) continue;
         bool is_broken = low[0] < g_history_price[i][0][l];
         ENUM_LINE_STYLE style = (l==0 && !is_broken) ? STYLE_SOLID : BrokenLineStyle;
         
         datetime pivot_time = g_history_time[i][0][l];
         double pivot_price = g_history_price[i][0][l];
         string label_text = g_Label[i]+" L";
         string base_name = "HL_"+g_Label[i]+"_L_"+(string)pivot_time;

         string line_name= base_name+"_line";
         datetime time2=pivot_time+PeriodSeconds(_Period);
         ObjectCreate(0,line_name,OBJ_TREND,0,pivot_time,pivot_price,time2,pivot_price);
         ObjectSetInteger(0,line_name,OBJPROP_COLOR,g_LowColor[i]);
         ObjectSetInteger(0,line_name,OBJPROP_WIDTH,LineWidth);
         ObjectSetInteger(0,line_name,OBJPROP_RAY_RIGHT,true);
         ObjectSetInteger(0,line_name,OBJPROP_STYLE,style);

         string label_name= base_name+"_label";
         double p_offset=Label_Y_Offset_Pts*_Point;
         ObjectCreate(0,label_name,OBJ_TEXT,0,pivot_time,pivot_price-p_offset);
         ObjectSetString(0,label_name,OBJPROP_TEXT,label_text);
         ObjectSetInteger(0,label_name,OBJPROP_COLOR,g_LowColor[i]);
         ObjectSetInteger(0,label_name,OBJPROP_FONTSIZE,LabelFontSize);
         ObjectSetInteger(0,label_name,OBJPROP_ANCHOR,ANCHOR_LEFT_UPPER);
        }
     }
   ChartRedraw();
  }
//+------------------------------------------------------------------+
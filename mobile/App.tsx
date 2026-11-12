import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, SafeAreaView,
  ScrollView, StatusBar, StyleSheet, Text, TextInput, View
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as WebBrowser from "expo-web-browser";
import * as Google from "expo-auth-session/providers/google";
import {
  createUserWithEmailAndPassword, onAuthStateChanged, signInWithEmailAndPassword,
  signOut, User
} from "firebase/auth";
import { auth, firebaseConfigured } from "./src/firebase";
import { analyzeResume } from "./src/api";
import { C } from "./src/theme";

WebBrowser.maybeCompleteAuthSession();

type Report = any;

function Button({ title, onPress, secondary=false, disabled=false }: any) {
  return <Pressable disabled={disabled} onPress={onPress} style={[styles.button, secondary && styles.buttonSecondary, disabled && {opacity:.55}]}>
    <Text style={[styles.buttonText, secondary && {color:C.ink}]}>{title}</Text>
  </Pressable>;
}
function Label({children}: any) { return <Text style={styles.label}>{children}</Text>; }
function Card({children}: any) { return <View style={styles.card}>{children}</View>; }

export default function App() {
  const [user, setUser] = useState<User|null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login"|"signup">("login");
  const [job, setJob] = useState("");
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Report|null>(null);
  const [fileName, setFileName] = useState("");
  const [showScanner, setShowScanner] = useState(false);

  const [request, response, promptAsync] = Google.useAuthRequest({
    webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
    androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
    scopes: ["openid", "profile", "email"],
  });

  useEffect(() => {
    if (!auth) { setAuthReady(true); return; }
    return onAuthStateChanged(auth, (u) => { setUser(u); setAuthReady(true); });
  }, []);

  useEffect(() => {
    const signInGoogle = async () => {
      if (response?.type !== "success" || !response.authentication?.idToken || !auth) return;
      try {
        const { GoogleAuthProvider, signInWithCredential } = await import("firebase/auth");
        const credential = GoogleAuthProvider.credential(response.authentication.idToken);
        await signInWithCredential(auth, credential);
      } catch (e:any) { Alert.alert("Google sign-in failed", e.message || "Please try again."); }
    };
    signInGoogle();
  }, [response]);

  const handleEmailAuth = async () => {
    if (!auth) return Alert.alert("Firebase not configured", "Add your Firebase settings to mobile/.env first.");
    if (!email.trim() || password.length < 6) return Alert.alert("Check your details", "Enter a valid email and a password of at least 6 characters.");
    setBusy(true);
    try {
      if (authMode === "login") await signInWithEmailAndPassword(auth, email.trim(), password);
      else await createUserWithEmailAndPassword(auth, email.trim(), password);
      setPassword("");
    } catch (e:any) { Alert.alert("Authentication failed", e.message || "Please try again."); }
    finally { setBusy(false); }
  };

  const pickAndAnalyze = async () => {
    if (!user) return Alert.alert("Sign in required", "Please sign in before scanning your resume.");
    const picked = await DocumentPicker.getDocumentAsync({
      type: ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
      copyToCacheDirectory: true,
    });
    if (picked.canceled || !picked.assets?.[0]) return;
    const asset = picked.assets[0];
    setFileName(asset.name);
    setBusy(true);
    setReport(null);
    try {
      const result = await analyzeResume(asset.uri, asset.name, asset.mimeType || "application/octet-stream", job);
      setReport(result);
      setShowScanner(false);
    } catch (e:any) { Alert.alert("Couldn't analyze resume", e.message || "Please try another file."); }
    finally { setBusy(false); }
  };

  const reset = () => { setReport(null); setJob(""); setFileName(""); setShowScanner(false); };

  if (!authReady) return <SafeAreaView style={styles.center}><ActivityIndicator color={C.blue}/></SafeAreaView>;

  return <SafeAreaView style={styles.safe}>
    <StatusBar barStyle="dark-content" />
    <View style={styles.topbar}>
      <View style={styles.brandMark}><Text style={{color:"#fff",fontWeight:"800",fontSize:17}}>R</Text></View>
      <View style={{flex:1}}><Text style={styles.brand}>Resume Analyzer</Text><Text style={styles.brandSub}>CAREER TOOLS</Text></View>
      {user ? <Pressable onPress={() => { signOut(auth!); reset(); }}><Text style={styles.link}>Sign out</Text></Pressable> : <Text style={styles.status}>Guest</Text>}
    </View>

    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      {!user ? <View>
        <View style={styles.hero}>
          <Text style={styles.eyebrow}>A CLEARER WAY TO APPLY</Text>
          <Text style={styles.heroTitle}>Know what your resume is saying.</Text>
          <Text style={styles.body}>Get a transparent resume score, understand every deduction, and see how to improve before you apply.</Text>
          <View style={styles.heroPills}><Text style={styles.pill}>ATS-focused</Text><Text style={styles.pill}>Actionable feedback</Text><Text style={styles.pill}>Private scans</Text></View>
        </View>
        <Card>
          <Text style={styles.cardTitle}>{authMode === "login" ? "Welcome back" : "Create your account"}</Text>
          <Text style={styles.bodySmall}>Sign in to unlock Resume Analyzer.</Text>
          {!firebaseConfigured && <Text style={styles.warning}>Firebase setup required. Add the values from mobile/.env.example to mobile/.env.</Text>}
          <Button title="Continue with Google" onPress={() => promptAsync()} disabled={!request || !firebaseConfigured || busy}/>
          <View style={styles.separator}><View style={styles.rule}/><Text style={styles.muted}>OR WITH EMAIL</Text><View style={styles.rule}/></View>
          <Label>Email address</Label><TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="you@example.com" style={styles.input}/>
          <Label>Password</Label><TextInput value={password} onChangeText={setPassword} secureTextEntry placeholder="At least 6 characters" style={styles.input}/>
          <Button title={busy ? "Please wait..." : authMode === "login" ? "Sign in" : "Create account"} onPress={handleEmailAuth} disabled={busy || !firebaseConfigured}/>
          <Pressable onPress={() => setAuthMode(authMode === "login" ? "signup" : "login")} style={{padding:12}}>
            <Text style={styles.linkCenter}>{authMode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}</Text>
          </Pressable>
        </Card>
      </View> : report ? <ReportView report={report} fileName={fileName} onBack={reset}/> : <View>
        <View style={styles.hero}>
          <Text style={styles.eyebrow}>YOUR CAREER, MORE CLEARLY</Text>
          <Text style={styles.heroTitle}>Make your next application stronger.</Text>
          <Text style={styles.body}>Analyze your resume against a consistent quality rubric, then optionally compare it with a job description.</Text>
        </View>
        <Card>
          <View style={styles.rowBetween}><Text style={styles.cardTitle}>Resume Analyzer</Text><Text style={styles.newTag}>V1</Text></View>
          <Text style={styles.bodySmall}>Upload a PDF or DOCX file. Maximum size: 8 MB.</Text>
          <View style={styles.uploadBox}>
            <Text style={styles.uploadIcon}>↑</Text>
            <Text style={styles.uploadTitle}>Ready to review your resume?</Text>
            <Text style={styles.muted}>PDF or DOCX · Up to 8 MB</Text>
            <Button title={busy ? "Analyzing..." : "Choose resume"} onPress={pickAndAnalyze} disabled={busy}/>
            {busy && <ActivityIndicator color={C.blue} style={{marginTop:12}}/>}
          </View>
          <Label>Job description (optional)</Label>
          <TextInput value={job} onChangeText={setJob} multiline textAlignVertical="top" placeholder="Paste the job description here to get a separate job-match score..." style={[styles.input,styles.textarea]}/>
          <Text style={styles.privacy}>Your scan isn't saved to history. The resume is processed to generate this report and is not retained by this V1 app.</Text>
        </Card>
        <View style={styles.sectionHeading}><Text style={styles.sectionTitle}>What you'll get</Text></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>01</Text><View style={{flex:1}}><Text style={styles.featureTitle}>A clear score</Text><Text style={styles.bodySmall}>See your overall resume quality and optional job match.</Text></View></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>02</Text><View style={{flex:1}}><Text style={styles.featureTitle}>Transparent deductions</Text><Text style={styles.bodySmall}>Understand exactly which areas lost points and why.</Text></View></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>03</Text><View style={{flex:1}}><Text style={styles.featureTitle}>Practical next steps</Text><Text style={styles.bodySmall}>Get specific improvements grounded in your resume.</Text></View></View>
      </View>}
      <Text style={styles.footer}>RESUME ANALYZER · VERSION 1.0</Text>
    </ScrollView>
  </SafeAreaView>;
}

function Score({value, label}: any) {
  const color = value >= 80 ? C.green : value >= 60 ? C.blue : C.amber;
  return <View style={styles.scoreCard}>
    <View style={[styles.scoreCircle,{borderColor:color}]}><Text style={[styles.scoreNumber,{color}]}>{value}</Text><Text style={styles.scoreOutOf}>/100</Text></View>
    <Text style={styles.scoreLabel}>{label}</Text>
  </View>;
}
function ReportView({report,fileName,onBack}: any) {
  const q = report.quality;
  const j = report.job_match;
  return <View>
    <Text style={styles.eyebrow}>ANALYSIS COMPLETE</Text>
    <Text style={styles.heroTitle}>Your resume report</Text>
    <Text style={styles.bodySmall}>{fileName}</Text>
    <View style={styles.scoreGrid}><Score value={q.score} label="Resume quality"/>{j && <Score value={j.score} label="Job match"/>}</View>
    <Card><Text style={styles.cardTitle}>Resume quality breakdown</Text><Text style={styles.bodySmall}>{q.summary}</Text>
      {q.breakdown.map((item:any) => <Breakdown key={item.key} item={item}/>)}
    </Card>
    {j && <Card><Text style={styles.cardTitle}>Job-specific match</Text><Text style={styles.bodySmall}>{j.summary}</Text>
      {j.breakdown.map((item:any) => <Breakdown key={item.key} item={item}/>)}
      {j.missing_skills?.length > 0 && <><Text style={styles.subhead}>Skills not detected</Text><View style={styles.skillWrap}>{j.missing_skills.map((s:string)=><Text key={s} style={styles.missingSkill}>{s}</Text>)}</View></>}
      {j.matched_skills?.length > 0 && <><Text style={styles.subhead}>Skills detected</Text><View style={styles.skillWrap}>{j.matched_skills.map((s:string)=><Text key={s} style={styles.matchedSkill}>{s}</Text>)}</View></>}
    </Card>}
    <Card><Text style={styles.cardTitle}>Where to improve</Text>
      {q.findings.length === 0 && <Text style={styles.bodySmall}>No major deductions were identified by this rubric.</Text>}
      {q.findings.map((f:any)=><Finding key={f.code} finding={f}/>)}
    </Card>
    {j?.findings?.length > 0 && <Card><Text style={styles.cardTitle}>Job match recommendations</Text>{j.findings.map((f:any)=><Finding key={f.code} finding={f}/>)}</Card>}
    <Card><Text style={styles.cardTitle}>Your next steps</Text>{q.top_suggestions.map((s:string,i:number)=><View key={i} style={styles.suggestion}><Text style={styles.suggestionNum}>{i+1}</Text><Text style={styles.suggestionText}>{s}</Text></View>)}</Card>
    <Text style={styles.privacy}>This score is an explainable estimate based on our V1 rubric, not a guarantee of how a particular employer's ATS will rank your resume. This scan is not saved.</Text>
    <Button title="Analyze another resume" onPress={onBack}/>
  </View>;
}
function Breakdown({item}: any) {
  const pct = item.possible ? item.earned/item.possible : 0;
  return <View style={styles.breakdown}>
    <View style={styles.rowBetween}><Text style={styles.breakLabel}>{item.label}</Text><Text style={styles.breakValue}>{item.earned}/{item.possible}</Text></View>
    <View style={styles.barBg}><View style={[styles.barFill,{width:`${pct*100}%`} as any]}/></View>
    {item.deducted > 0 && <Text style={styles.deduction}>−{item.deducted} points</Text>}
  </View>;
}
function Finding({finding}: any) {
  const color = finding.severity === "high" ? C.red : finding.severity === "medium" ? C.amber : C.muted;
  return <View style={styles.finding}>
    <View style={styles.rowBetween}><Text style={styles.findingTitle}>{finding.title}</Text>{finding.deduction > 0 && <Text style={[styles.deduction,{color}]}>−{finding.deduction}</Text>}</View>
    {finding.evidence && <Text style={styles.evidence}>Evidence: {finding.evidence}</Text>}
    <Text style={styles.recommendation}>{finding.recommendation}</Text>
  </View>;
}

const styles = StyleSheet.create({
  safe:{flex:1,backgroundColor:C.soft}, center:{flex:1,alignItems:"center",justifyContent:"center"},
  topbar:{height:66,paddingHorizontal:20,flexDirection:"row",alignItems:"center",gap:11,borderBottomWidth:1,borderColor:C.line,backgroundColor:C.white},
  brandMark:{width:36,height:36,borderRadius:11,backgroundColor:C.navy,alignItems:"center",justifyContent:"center"},
  brand:{fontSize:15,fontWeight:"800",color:C.ink},brandSub:{fontSize:9,letterSpacing:1.6,color:C.muted,marginTop:2},
  status:{fontSize:12,color:C.muted},link:{color:C.blue,fontWeight:"700",fontSize:13},
  content:{padding:20,paddingBottom:36},hero:{paddingTop:13,paddingBottom:22},
  eyebrow:{fontSize:10,fontWeight:"800",letterSpacing:1.7,color:C.blue,marginBottom:10},
  heroTitle:{fontSize:31,lineHeight:37,fontWeight:"800",letterSpacing:-.8,color:C.ink,marginBottom:10},
  body:{fontSize:14,lineHeight:22,color:C.muted},bodySmall:{fontSize:12,lineHeight:18,color:C.muted,marginTop:5},
  heroPills:{flexDirection:"row",flexWrap:"wrap",gap:7,marginTop:15},
  pill:{fontSize:10,color:C.navy,backgroundColor:"#E8EDF5",paddingHorizontal:10,paddingVertical:6,borderRadius:20,fontWeight:"600"},
  card:{backgroundColor:C.white,borderRadius:18,padding:18,marginBottom:14,borderWidth:1,borderColor:C.line},
  cardTitle:{fontSize:18,fontWeight:"800",color:C.ink},button:{backgroundColor:C.navy,paddingVertical:14,paddingHorizontal:16,borderRadius:12,alignItems:"center",marginTop:14},
  buttonSecondary:{backgroundColor:"#EEF1F5"},buttonText:{fontSize:14,fontWeight:"700",color:C.white},
  separator:{flexDirection:"row",alignItems:"center",gap:10,marginVertical:17},rule:{height:1,backgroundColor:C.line,flex:1},
  muted:{fontSize:10,color:C.muted},label:{fontSize:12,fontWeight:"700",color:C.ink,marginTop:14,marginBottom:7},
  input:{borderWidth:1,borderColor:C.line,borderRadius:11,paddingHorizontal:13,paddingVertical:12,fontSize:14,color:C.ink,backgroundColor:C.white},
  linkCenter:{textAlign:"center",color:C.blue,fontSize:12,fontWeight:"700"},warning:{color:C.amber,fontSize:11,lineHeight:17,marginTop:12},
  rowBetween:{flexDirection:"row",justifyContent:"space-between",alignItems:"center"},
  newTag:{backgroundColor:C.blueSoft,color:C.blue,fontWeight:"800",fontSize:10,paddingHorizontal:9,paddingVertical:5,borderRadius:20},
  uploadBox:{backgroundColor:"#F8FAFD",borderWidth:1,borderColor:"#DCE4F0",borderStyle:"dashed",borderRadius:14,padding:20,alignItems:"center",marginTop:16,marginBottom:10},
  uploadIcon:{fontSize:28,color:C.blue,fontWeight:"400"},uploadTitle:{fontSize:14,fontWeight:"800",color:C.ink,marginTop:8,marginBottom:4},
  textarea:{height:116,paddingTop:12},privacy:{fontSize:10,lineHeight:16,color:C.muted,marginTop:12},
  sectionHeading:{marginTop:12,marginBottom:10},sectionTitle:{fontSize:18,fontWeight:"800",color:C.ink},
  featureRow:{flexDirection:"row",gap:13,alignItems:"flex-start",paddingVertical:12,borderBottomWidth:1,borderBottomColor:C.line},
  featureIcon:{fontSize:12,fontWeight:"800",color:C.blue,backgroundColor:C.blueSoft,borderRadius:8,padding:9},
  featureTitle:{fontSize:13,fontWeight:"800",color:C.ink},footer:{fontSize:9,letterSpacing:1.5,textAlign:"center",color:"#9AA3B2",marginTop:16},
  scoreGrid:{flexDirection:"row",gap:12,marginBottom:14},scoreCard:{flex:1,backgroundColor:C.white,borderRadius:17,borderWidth:1,borderColor:C.line,padding:16,alignItems:"center"},
  scoreCircle:{width:94,height:94,borderRadius:47,borderWidth:5,alignItems:"center",justifyContent:"center"},
  scoreNumber:{fontSize:30,fontWeight:"900"},scoreOutOf:{fontSize:10,color:C.muted},scoreLabel:{fontSize:12,fontWeight:"700",color:C.ink,marginTop:10},
  breakdown:{marginTop:17},breakLabel:{fontSize:12,fontWeight:"700",color:C.ink},breakValue:{fontSize:12,fontWeight:"800",color:C.ink},
  barBg:{height:7,backgroundColor:"#EDF0F4",borderRadius:9,overflow:"hidden",marginTop:8},barFill:{height:7,backgroundColor:C.blue,borderRadius:9},
  deduction:{fontSize:10,color:C.red,fontWeight:"700",marginTop:4},finding:{paddingVertical:13,borderBottomWidth:1,borderBottomColor:C.line},
  findingTitle:{fontSize:12,fontWeight:"800",color:C.ink,flex:1,paddingRight:8},evidence:{fontSize:10,color:C.muted,marginTop:6,fontStyle:"italic"},
  recommendation:{fontSize:12,lineHeight:18,color:C.ink,marginTop:7},subhead:{fontSize:12,fontWeight:"800",color:C.ink,marginTop:16,marginBottom:8},
  skillWrap:{flexDirection:"row",flexWrap:"wrap",gap:7},missingSkill:{fontSize:10,color:C.red,backgroundColor:"#FFF0F0",paddingHorizontal:9,paddingVertical:6,borderRadius:20},
  matchedSkill:{fontSize:10,color:C.green,backgroundColor:"#EAF7F1",paddingHorizontal:9,paddingVertical:6,borderRadius:20},
  suggestion:{flexDirection:"row",gap:10,marginTop:13,alignItems:"flex-start"},suggestionNum:{width:22,height:22,textAlign:"center",textAlignVertical:"center",borderRadius:11,overflow:"hidden",backgroundColor:C.blueSoft,color:C.blue,fontWeight:"800",fontSize:11},
  suggestionText:{flex:1,fontSize:12,lineHeight:18,color:C.ink},
});

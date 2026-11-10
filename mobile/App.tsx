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
  return <Pressable disabled={disabled} onPress={onPress} style={({pressed}) => [styles.button, secondary && styles.buttonSecondary, disabled && {opacity:.55}, pressed && !disabled && styles.buttonPressed]}>
    <Text style={[styles.buttonText, secondary && {color:C.ink}]}>{title}</Text>
  </Pressable>;
}
function Label({children}: any) { return <Text style={styles.label}>{children}</Text>; }
function Card({children}: any) { return <View style={styles.card}>{children}</View>; }

export default function App() {
  const [user, setUser] = useState<User|null>(null);
  const [isGuest, setIsGuest] = useState(false);
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
    return onAuthStateChanged(auth, (u) => { setUser(u); if (u) setIsGuest(false); setAuthReady(true); });
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
    if (!user && !isGuest) return Alert.alert("Sign in required", "Please sign in or continue as a guest before scanning.");
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
    <StatusBar barStyle="dark-content"/>
    <View style={styles.topbar}>
      <View style={styles.brandMark}><Text style={styles.brandMarkText}>C</Text></View>
      <View style={{flex:1}}><Text style={styles.brand}>CareerLeap</Text><Text style={styles.brandSub}>CAREER COMPANION</Text></View>
      {user ? <Pressable hitSlop={12} onPress={() => { signOut(auth!); reset(); }}><Text style={styles.link}>Sign out</Text></Pressable> : isGuest ? <Pressable hitSlop={12} onPress={() => { reset(); setIsGuest(false); }}><Text style={styles.link}>Exit guest</Text></Pressable> : null}
    </View>

    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      {!user && !isGuest ? <View>
        <View style={styles.hero}>
          <View style={styles.heroAccent}><View style={styles.heroAccentDot}/><Text style={styles.heroAccentText}>CAREER CLARITY STARTS HERE</Text></View>
          <Text style={styles.heroTitle}>Put your best resume forward.</Text>
          <Text style={styles.body}>Get a clear picture of your resume's strengths, understand what needs work, and apply with more confidence.</Text>
          <View style={styles.heroPills}><Text style={styles.pill}>ATS-aware insights</Text><Text style={styles.pill}>Evidence-led feedback</Text><Text style={styles.pill}>Private scans</Text></View>
        </View>
        <Card>
          <Text style={styles.cardTitle}>{authMode === "login" ? "Welcome back" : "Create your account"}</Text>
          <Text style={styles.bodySmall}>Sign in to access your resume analysis workspace.</Text>
          {!firebaseConfigured && <Text style={styles.warning}>Firebase setup required. Add the values from mobile/.env.example to mobile/.env.</Text>}
          <Button title="Continue with Google" onPress={() => promptAsync()} disabled={!request || !firebaseConfigured || busy}/>
          <View style={styles.separator}><View style={styles.rule}/><Text style={styles.muted}>OR CONTINUE WITH EMAIL</Text><View style={styles.rule}/></View>
          <Label>Email address</Label><TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" placeholder="you@example.com" placeholderTextColor="#98A2B3" style={styles.input}/>
          <Label>Password</Label><TextInput value={password} onChangeText={setPassword} secureTextEntry autoComplete={authMode === "login" ? "current-password" : "new-password"} placeholder="At least 6 characters" placeholderTextColor="#98A2B3" style={styles.input}/>
          <Button title={busy ? "Please wait..." : authMode === "login" ? "Sign in" : "Create account"} onPress={handleEmailAuth} disabled={busy || !firebaseConfigured}/>
          <Pressable onPress={() => setAuthMode(authMode === "login" ? "signup" : "login")} style={styles.authSwitch}>
            <Text style={styles.linkCenter}>{authMode === "login" ? "New to CareerLeap? Create an account" : "Already have an account? Sign in"}</Text>
          </Pressable>
          <Pressable onPress={() => setIsGuest(true)} style={styles.guestSwitch}>
            <Text style={styles.linkCenter}>Continue as guest</Text>
            <Text style={styles.guestHint}>Try resume analysis without creating an account</Text>
          </Pressable>
        </Card>
      </View> : report ? <ReportView report={report} fileName={fileName} onBack={reset}/> : <View>
        <View style={styles.hero}>
          <View style={styles.heroAccent}><View style={styles.heroAccentDot}/><Text style={styles.heroAccentText}>YOUR NEXT OPPORTUNITY</Text></View>
          <Text style={styles.heroTitle}>Make every application count.</Text>
          <Text style={styles.body}>Understand your resume quality and see how closely your experience aligns with the role you're targeting.</Text>
        </View>
        <Card>
          <View style={styles.rowBetween}><View><Text style={styles.cardTitle}>Resume analysis</Text><Text style={styles.bodySmall}>A focused review, built around evidence.</Text></View><Text style={styles.newTag}>BETA</Text></View>
          <View style={styles.uploadBox}>
            <View style={styles.uploadIconWrap}><Text style={styles.uploadIcon}>↑</Text></View>
            <Text style={styles.uploadTitle}>Upload your resume</Text>
            <Text style={styles.muted}>PDF or DOCX · Maximum 8 MB</Text>
            <Button title={busy ? "Analyzing..." : "Choose a file"} onPress={pickAndAnalyze} disabled={busy}/>
            {busy && <ActivityIndicator color={C.blue} style={{marginTop:14}}/>}
          </View>
          <View style={styles.optionalHeader}><Label>Target job description</Label><Text style={styles.optionalTag}>OPTIONAL</Text></View>
          <TextInput value={job} onChangeText={setJob} multiline textAlignVertical="top" placeholder="Paste the job description to get a separate job-match assessment..." placeholderTextColor="#98A2B3" style={[styles.input,styles.textarea]}/>
          <View style={styles.privacyRow}><Text style={styles.privacyIcon}>⌑</Text><Text style={styles.privacy}>Your scan isn't saved to history. The resume is processed to generate this report and is not retained by this V1 app.</Text></View>
        </Card>
        <View style={styles.sectionHeading}><Text style={styles.sectionTitle}>A clearer view of your resume</Text><Text style={styles.bodySmall}>Useful feedback, without the guesswork.</Text></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>01</Text><View style={{flex:1}}><Text style={styles.featureTitle}>Understand your score</Text><Text style={styles.bodySmall}>See the quality breakdown and optional job match.</Text></View></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>02</Text><View style={{flex:1}}><Text style={styles.featureTitle}>See the evidence</Text><Text style={styles.bodySmall}>Understand which areas need attention and why.</Text></View></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>03</Text><View style={{flex:1}}><Text style={styles.featureTitle}>Know what to improve</Text><Text style={styles.bodySmall}>Get practical suggestions grounded in your resume.</Text></View></View>
      </View>}
      <Text style={styles.footer}>CAREERLEAP  ·  BUILT FOR YOUR NEXT STEP</Text>
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
    <View style={styles.reportHeading}>
      <View style={styles.heroAccent}><View style={styles.heroAccentDot}/><Text style={styles.heroAccentText}>ANALYSIS COMPLETE</Text></View>
      <Text style={styles.heroTitle}>Your resume, reviewed.</Text>
      <Text style={styles.bodySmall} numberOfLines={1}>{fileName}</Text>
    </View>
    <View style={styles.scoreGrid}><Score value={q.score} label="Resume quality"/>{j && <Score value={j.score} label="Job match"/>}</View>
    <Card><Text style={styles.cardTitle}>Resume quality</Text><Text style={styles.bodySmall}>{q.summary}</Text>
      {q.breakdown.map((item:any) => <Breakdown key={item.key} item={item}/>)}
    </Card>
    {j && <Card><Text style={styles.cardTitle}>Job-specific match</Text><Text style={styles.bodySmall}>{j.summary}</Text>
      {j.breakdown.map((item:any) => <Breakdown key={item.key} item={item}/>)}
      {j.missing_skills?.length > 0 && <><Text style={styles.subhead}>Not detected in your resume</Text><View style={styles.skillWrap}>{j.missing_skills.map((s:string)=><Text key={s} style={styles.missingSkill}>{s}</Text>)}</View></>}
      {j.matched_skills?.length > 0 && <><Text style={styles.subhead}>Evidence detected</Text><View style={styles.skillWrap}>{j.matched_skills.map((s:string)=><Text key={s} style={styles.matchedSkill}>{s}</Text>)}</View></>}
    </Card>}
    <Card><Text style={styles.cardTitle}>Areas to strengthen</Text>
      {q.findings.length === 0 && <Text style={styles.bodySmall}>No major deductions were identified by this rubric.</Text>}
      {q.findings.map((f:any)=><Finding key={f.code} finding={f}/>)}
    </Card>
    {j?.findings?.length > 0 && <Card><Text style={styles.cardTitle}>Job match recommendations</Text>{j.findings.map((f:any)=><Finding key={f.code} finding={f}/>)}</Card>}
    <Card><Text style={styles.cardTitle}>Recommended next steps</Text>{q.top_suggestions.map((s:string,i:number)=><View key={i} style={styles.suggestion}><Text style={styles.suggestionNum}>{i+1}</Text><Text style={styles.suggestionText}>{s}</Text></View>)}</Card>
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
  topbar:{height:70,paddingHorizontal:22,flexDirection:"row",alignItems:"center",gap:12,borderBottomWidth:1,borderColor:C.line,backgroundColor:C.white},
  brandMark:{width:40,height:40,borderRadius:13,backgroundColor:C.navy,alignItems:"center",justifyContent:"center"},
  brandMarkText:{color:"#FFFFFF",fontWeight:"900",fontSize:20,letterSpacing:-1},
  brand:{fontSize:17,fontWeight:"800",color:C.ink,letterSpacing:-.35},brandSub:{fontSize:9,letterSpacing:1.55,color:C.muted,marginTop:3,fontWeight:"700"},
  status:{fontSize:11,color:C.muted,backgroundColor:"#F2F4F7",paddingHorizontal:10,paddingVertical:6,borderRadius:20},link:{color:C.blue,fontWeight:"700",fontSize:13},
  content:{paddingHorizontal:20,paddingTop:8,paddingBottom:42},hero:{paddingTop:22,paddingBottom:24},
  heroAccent:{flexDirection:"row",alignItems:"center",gap:7,marginBottom:12},
  heroAccentDot:{width:7,height:7,borderRadius:4,backgroundColor:C.blue},
  heroAccentText:{fontSize:10,fontWeight:"800",letterSpacing:1.5,color:C.blue},
  heroTitle:{fontSize:32,lineHeight:38,fontWeight:"800",letterSpacing:-1.05,color:C.ink,marginBottom:10},
  body:{fontSize:14,lineHeight:22,color:C.muted},bodySmall:{fontSize:12,lineHeight:18,color:C.muted,marginTop:5},
  heroPills:{flexDirection:"row",flexWrap:"wrap",gap:7,marginTop:17},
  pill:{fontSize:10,color:"#344B7A",backgroundColor:"#EDF1FA",paddingHorizontal:10,paddingVertical:7,borderRadius:20,fontWeight:"700"},
  card:{backgroundColor:C.white,borderRadius:20,padding:19,marginBottom:16,borderWidth:1,borderColor:C.line,elevation:2,shadowColor:"#172B4D",shadowOpacity:.045,shadowRadius:12,shadowOffset:{width:0,height:4}},
  cardTitle:{fontSize:18,fontWeight:"800",color:C.ink,letterSpacing:-.35},
  button:{backgroundColor:C.navy,paddingVertical:15,paddingHorizontal:18,borderRadius:13,alignItems:"center",marginTop:15,elevation:2,shadowColor:C.navy,shadowOpacity:.13,shadowRadius:5,shadowOffset:{width:0,height:3}},
  buttonPressed:{opacity:.86,transform:[{scale:.99}]},buttonSecondary:{backgroundColor:"#EEF1F6",elevation:0,shadowOpacity:0},buttonText:{fontSize:14,fontWeight:"800",color:C.white,letterSpacing:.1},
  separator:{flexDirection:"row",alignItems:"center",gap:10,marginVertical:19},rule:{height:1,backgroundColor:C.line,flex:1},
  muted:{fontSize:10,color:C.muted},label:{fontSize:12,fontWeight:"700",color:C.ink,marginTop:15,marginBottom:8},
  input:{borderWidth:1,borderColor:"#DDE2EA",borderRadius:12,paddingHorizontal:14,paddingVertical:13,fontSize:14,color:C.ink,backgroundColor:"#FCFCFD"},
  authSwitch:{paddingVertical:13},guestSwitch:{paddingTop:9,paddingBottom:3,alignItems:"center"},guestHint:{fontSize:10,color:C.muted,marginTop:5},linkCenter:{textAlign:"center",color:C.blue,fontSize:12,fontWeight:"700"},
  warning:{color:C.amber,fontSize:11,lineHeight:17,marginTop:12,backgroundColor:"#FFF8EB",padding:10,borderRadius:9},
  rowBetween:{flexDirection:"row",justifyContent:"space-between",alignItems:"center"},
  newTag:{backgroundColor:C.blueSoft,color:C.blue,fontWeight:"800",fontSize:9,letterSpacing:1,paddingHorizontal:10,paddingVertical:7,borderRadius:20,overflow:"hidden"},
  uploadBox:{backgroundColor:"#F8FAFF",borderWidth:1,borderColor:"#D9E2F4",borderStyle:"dashed",borderRadius:16,padding:21,alignItems:"center",marginTop:19,marginBottom:9},
  uploadIconWrap:{width:46,height:46,borderRadius:15,backgroundColor:C.blueSoft,alignItems:"center",justifyContent:"center",marginBottom:10},
  uploadIcon:{fontSize:26,color:C.blue,fontWeight:"500",marginTop:-3},
  uploadTitle:{fontSize:15,fontWeight:"800",color:C.ink,marginBottom:5},
  optionalHeader:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginTop:8},
  optionalTag:{fontSize:9,color:C.muted,letterSpacing:1,fontWeight:"800",marginTop:13},
  textarea:{height:116,paddingTop:13,textAlignVertical:"top"},
  privacyRow:{flexDirection:"row",alignItems:"flex-start",gap:8,marginTop:13},
  privacyIcon:{fontSize:17,color:C.green,fontWeight:"800",marginTop:-2},
  privacy:{flex:1,fontSize:10,lineHeight:16,color:C.muted,marginTop:12},
  sectionHeading:{marginTop:17,marginBottom:7},sectionTitle:{fontSize:18,fontWeight:"800",color:C.ink,letterSpacing:-.4},
  featureRow:{flexDirection:"row",gap:13,alignItems:"flex-start",paddingVertical:14,borderBottomWidth:1,borderBottomColor:C.line},
  featureIcon:{fontSize:11,fontWeight:"900",color:C.blue,backgroundColor:C.blueSoft,borderRadius:9,paddingHorizontal:9,paddingVertical:8,overflow:"hidden"},
  featureTitle:{fontSize:13,fontWeight:"800",color:C.ink},
  footer:{fontSize:9,letterSpacing:1.35,textAlign:"center",color:"#98A2B3",marginTop:22,fontWeight:"700"},
  reportHeading:{paddingTop:20,paddingBottom:17},scoreGrid:{flexDirection:"row",gap:12,marginBottom:16},
  scoreCard:{flex:1,backgroundColor:C.white,borderRadius:18,borderWidth:1,borderColor:C.line,padding:17,alignItems:"center",elevation:1,shadowColor:"#172B4D",shadowOpacity:.04,shadowRadius:8,shadowOffset:{width:0,height:3}},
  scoreCircle:{width:96,height:96,borderRadius:48,borderWidth:5,alignItems:"center",justifyContent:"center"},
  scoreNumber:{fontSize:31,fontWeight:"900",letterSpacing:-1},scoreOutOf:{fontSize:10,color:C.muted,marginTop:-2},scoreLabel:{fontSize:12,fontWeight:"800",color:C.ink,marginTop:11},
  breakdown:{marginTop:18},breakLabel:{fontSize:12,fontWeight:"700",color:C.ink},breakValue:{fontSize:12,fontWeight:"800",color:C.ink},
  barBg:{height:8,backgroundColor:"#EEF0F4",borderRadius:9,overflow:"hidden",marginTop:9},barFill:{height:8,backgroundColor:C.blue,borderRadius:9},
  deduction:{fontSize:10,color:C.red,fontWeight:"700",marginTop:5},finding:{paddingVertical:14,borderBottomWidth:1,borderBottomColor:C.line},
  findingTitle:{fontSize:13,fontWeight:"800",color:C.ink,flex:1,paddingRight:8},evidence:{fontSize:10,color:C.muted,marginTop:7,fontStyle:"italic",lineHeight:16},
  recommendation:{fontSize:12,lineHeight:19,color:"#344054",marginTop:8},subhead:{fontSize:12,fontWeight:"800",color:C.ink,marginTop:17,marginBottom:9},
  skillWrap:{flexDirection:"row",flexWrap:"wrap",gap:7},
  missingSkill:{fontSize:10,color:"#B42318",backgroundColor:"#FEF3F2",paddingHorizontal:10,paddingVertical:7,borderRadius:20,overflow:"hidden",fontWeight:"600"},
  matchedSkill:{fontSize:10,color:"#067647",backgroundColor:"#ECFDF3",paddingHorizontal:10,paddingVertical:7,borderRadius:20,overflow:"hidden",fontWeight:"600"},
  suggestion:{flexDirection:"row",gap:11,marginTop:15,alignItems:"flex-start"},
  suggestionNum:{width:24,height:24,textAlign:"center",textAlignVertical:"center",borderRadius:12,overflow:"hidden",backgroundColor:C.blueSoft,color:C.blue,fontWeight:"900",fontSize:11},
  suggestionText:{flex:1,fontSize:12,lineHeight:19,color:"#344054"},
});
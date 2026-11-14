import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator, Alert, Animated, AppState, KeyboardAvoidingView, Platform, Pressable, SafeAreaView,
  ScrollView, StatusBar, StyleSheet, Text, TextInput, View
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import {
  createUserWithEmailAndPassword, onAuthStateChanged, signInWithEmailAndPassword,
  signOut, User
} from "firebase/auth";
import { auth, firebaseConfigured } from "./src/firebase";
import { analyzeResume } from "./src/api";
import { DARK_THEME, LIGHT_THEME } from "./src/theme";


// Firebase refresh tokens can keep a user signed in indefinitely. Enforce a fixed 24-hour session lifetime using the original authentication timestamp.
const SESSION_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const PASSWORD_RULE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9\s]).{8,}$/;

type Report = any;
function firebaseAuthMessage(error: any) {
  const code = error?.code || "";
  if (code.includes("CONFIGURATION_NOT_FOUND") || code === "auth/operation-not-allowed") {
    return "Firebase Authentication is not fully configured. In Firebase Console, open Authentication → Sign-in method and enable Email/Password, then try again.";
  }
  if (code === "auth/invalid-api-key" || code === "auth/api-key-not-valid") {
    return "The Firebase API key is invalid. Check EXPO_PUBLIC_FIREBASE_API_KEY in mobile/.env and restart Expo.";
  }
  if (code === "auth/network-request-failed") {
    return "Couldn't reach Firebase. Check your internet connection and try again.";
  }
  return error?.message || "Please try again.";
}


const ROLE_TEMPLATES = [
  {
    title: "Software Engineer",
    jd: `We are looking for a Software Engineer to design, develop, test, and maintain reliable software applications. You will collaborate with product managers, designers, and engineers to understand requirements and deliver maintainable solutions. Responsibilities include writing clean and efficient code, designing APIs and data models, debugging issues, reviewing code, improving application performance, and contributing to technical discussions. You should have a strong foundation in data structures, algorithms, object-oriented programming, and software engineering principles. Experience with one or more programming languages, databases, version control, testing, and building or integrating APIs is valuable. We value problem-solving ability, clear communication, ownership, and a willingness to learn.`,
  },
  {
    title: "Frontend Engineer",
    jd: `We are looking for a Frontend Engineer to build responsive, accessible, and user-friendly web applications. You will translate product and design requirements into reusable UI components, integrate frontend applications with backend APIs, and improve performance and usability. Responsibilities include developing and maintaining interfaces, managing application state, handling browser compatibility, writing maintainable code and tests, debugging production issues, and collaborating with design and backend teams. Strong JavaScript and HTML/CSS fundamentals are expected. Experience with React or another modern frontend framework, TypeScript, responsive design, REST APIs, Git, and frontend testing is useful. We value attention to detail, problem-solving, and a focus on user experience.`,
  },
  {
    title: "Backend Engineer",
    jd: `We are looking for a Backend Engineer to design, build, and maintain scalable and reliable services. You will develop APIs and backend components, work with databases and data models, integrate external systems, and help ensure application security, performance, and reliability. Responsibilities include writing maintainable code, debugging and resolving service issues, designing efficient queries, implementing tests, participating in code reviews, and contributing to system design discussions. Strong programming, data structures, algorithms, and database fundamentals are expected. Experience with Java, Kotlin, Python, Node.js, or similar languages; REST APIs; SQL or NoSQL databases; distributed systems; and cloud platforms is valuable. We value ownership, sound engineering judgment, and collaboration.`,
  },
  {
    title: "Full Stack Developer",
    jd: `We are looking for a Full Stack Developer to build and maintain end-to-end web applications. You will develop responsive frontend experiences, implement backend services and APIs, integrate databases, and collaborate with cross-functional teams to deliver product features. Responsibilities include translating requirements into technical solutions, building reusable UI components, designing data models, writing tests, debugging issues, reviewing code, and improving application performance. Strong programming fundamentals and experience with JavaScript or TypeScript are expected. Experience with React or a similar frontend framework, backend technologies such as Node.js, Java, or Python, REST APIs, databases, Git, and cloud services is useful. We value adaptability, communication, and an end-to-end approach to problem-solving.`,
  },
  {
    title: "Machine Learning Engineer",
    jd: `We are looking for a Machine Learning Engineer to develop, evaluate, and deploy data-driven solutions. You will work with engineers, data scientists, and product teams to translate business problems into measurable machine learning tasks. Responsibilities include preparing and analyzing datasets, training and evaluating models, building reproducible experiments, improving model performance, deploying inference workflows, and monitoring model behavior. Strong Python, programming, data structures, statistics, and machine learning fundamentals are expected. Experience with common ML frameworks, data processing, model evaluation, SQL, APIs, and cloud or MLOps tooling is valuable. We value experimental rigor, clear communication, and the ability to explain technical trade-offs.`,
  },
  {
    title: "DevOps / Cloud Engineer",
    jd: `We are looking for a DevOps / Cloud Engineer to improve the reliability, scalability, and delivery of software systems. You will work with development teams to automate infrastructure and deployment workflows, monitor services, and improve operational practices. Responsibilities include maintaining CI/CD pipelines, managing cloud resources, automating repeatable tasks, monitoring application health, troubleshooting incidents, and applying security and access-control best practices. Strong Linux, scripting, networking, and problem-solving fundamentals are expected. Experience with AWS or another cloud platform, Docker, Kubernetes, Terraform, Git, observability tools, and CI/CD systems is useful. We value ownership, operational discipline, and collaboration across engineering teams.`,
  },
];

function Button({ title, onPress, secondary=false, disabled=false, styles, C }: any) {
  return <Pressable disabled={disabled} onPress={onPress} style={({pressed}) => [styles.button, secondary && styles.buttonSecondary, disabled && {opacity:.55}, pressed && !disabled && styles.buttonPressed]}>
    <Text style={[styles.buttonText, secondary && {color:C.ink}]}>{title}</Text>
  </Pressable>;
}
function Label({children, styles}: any) { return <Text style={styles.label}>{children}</Text>; }
function Card({children, styles}: any) { return <View style={styles.card}>{children}</View>; }

export default function App() {
  const [user, setUser] = useState<User|null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const C = darkMode ? DARK_THEME : LIGHT_THEME;
  const styles = useMemo(() => createStyles(C), [darkMode]);
  const [authReady, setAuthReady] = useState(false);
  const [showSplash, setShowSplash] = useState(true);
  const splashOpacity = useRef(new Animated.Value(1)).current;
  const splashScale = useRef(new Animated.Value(0.88)).current;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login"|"signup">("login");
  const [job, setJob] = useState("");
  const [selectedRole, setSelectedRole] = useState("");
  const [showRoleOptions, setShowRoleOptions] = useState(false);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Report|null>(null);
  const [fileName, setFileName] = useState("");
  const [selectedAsset, setSelectedAsset] = useState<DocumentPicker.DocumentPickerAsset | null>(null);
  const [showScanner, setShowScanner] = useState(false);

  const sessionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    Animated.spring(splashScale, { toValue: 1, speed: 14, bounciness: 5, useNativeDriver: true }).start();
  }, [splashScale]);

  useEffect(() => {
    if (!authReady) return;
    const timer = setTimeout(() => {
      Animated.timing(splashOpacity, {
        toValue: 0,
        duration: 380,
        useNativeDriver: true,
      }).start(({ finished }) => {
        if (finished) setShowSplash(false);
      });
    }, 850);
    return () => clearTimeout(timer);
  }, [authReady, splashOpacity]);

  useEffect(() => {
    const firebaseAuth = auth;
    if (!firebaseAuth) { setAuthReady(true); return; }
    let mounted = true;
    let checking = false;

    const clearSessionTimer = () => {
      if (sessionTimer.current) {
        clearTimeout(sessionTimer.current);
        sessionTimer.current = null;
      }
    };

    const validateSession = async (candidate: User) => {
      if (checking || !mounted) return;
      checking = true;
      try {
        const token = await candidate.getIdTokenResult();
        const authTime = Number(token.claims.auth_time) * 1000;
        if (!Number.isFinite(authTime) || Date.now() - authTime >= SESSION_MAX_AGE_MS) {
          clearSessionTimer();
          if (mounted) setUser(null);
          await signOut(firebaseAuth);
          return;
        }
        const remaining = SESSION_MAX_AGE_MS - (Date.now() - authTime);
        clearSessionTimer();
        sessionTimer.current = setTimeout(async () => {
          if (firebaseAuth.currentUser?.uid === candidate.uid) {
            setUser(null);
            await signOut(firebaseAuth);
          }
        }, remaining);
        if (mounted) setUser(candidate);
      } catch {
        // Fail closed if the current session cannot be verified.
        clearSessionTimer();
        if (mounted) setUser(null);
        if (firebaseAuth.currentUser?.uid === candidate.uid) await signOut(firebaseAuth);
      } finally {
        checking = false;
        if (mounted) setAuthReady(true);
      }
    };

    const unsubscribe = onAuthStateChanged(firebaseAuth, (candidate) => {
      clearSessionTimer();
      if (candidate) void validateSession(candidate);
      else {
        setUser(null);
        setAuthReady(true);
      }
    });
    const appStateSubscription = AppState.addEventListener("change", (state) => {
      if (state === "active" && firebaseAuth.currentUser) void validateSession(firebaseAuth.currentUser);
    });
    return () => {
      mounted = false;
      clearSessionTimer();
      unsubscribe();
      appStateSubscription.remove();
    };
  }, []);

  const handleEmailAuth = async () => {
    if (!auth) return Alert.alert("Firebase not configured", "Add your Firebase settings to mobile/.env first.");
    if (!email.trim()) return Alert.alert("Check your details", "Enter a valid email address.");
    if (authMode === "signup" && !PASSWORD_RULE.test(password)) {
      return Alert.alert("Choose a stronger password", "Use at least 8 characters with an uppercase letter, a lowercase letter, a number, and a special character.");
    }
    if (authMode === "login" && !password) return Alert.alert("Check your details", "Enter your password.");
    setBusy(true);
    try {
      if (authMode === "login") await signInWithEmailAndPassword(auth, email.trim(), password);
      else await createUserWithEmailAndPassword(auth, email.trim(), password);
      setPassword("");
    } catch (e:any) { Alert.alert("Authentication failed", firebaseAuthMessage(e)); }
    finally { setBusy(false); }
  };

  const pickResume = async () => {
    if (!user) return Alert.alert("Sign in required", "Please sign in before scanning.");
    try {
      const picked = await DocumentPicker.getDocumentAsync({
        type: ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        copyToCacheDirectory: true,
      });
      if (picked.canceled || !picked.assets?.[0]) return;
      const asset = picked.assets[0];
      setSelectedAsset(asset);
      setFileName(asset.name);
      setReport(null);
    } catch (e: any) {
      Alert.alert("Couldn't select resume", e.message || "Please try another file.");
    }
  };

  const scanResume = async () => {
    if (!user) return Alert.alert("Sign in required", "Please sign in before scanning.");
    if (!selectedAsset) return Alert.alert("Choose a resume", "Select a PDF or DOCX before scanning.");
    setBusy(true);
    setReport(null);
    try {
      const result = await analyzeResume(
        selectedAsset.uri,
        selectedAsset.name,
        selectedAsset.mimeType || "application/octet-stream",
        job,
        selectedAsset.file || null
      );
      setReport(result);
      setShowScanner(false);
    } catch (e: any) {
      Alert.alert("Couldn't analyze resume", e.message || "Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setReport(null);
    setJob("");
    setSelectedRole("");
    setShowRoleOptions(false);
    setFileName("");
    setSelectedAsset(null);
    setShowScanner(false);
  };

  if (!authReady || showSplash) return <SafeAreaView style={styles.splashSafe}>
    <StatusBar barStyle={darkMode ? "light-content" : "dark-content"} backgroundColor={C.soft}/>
    <Animated.View style={[styles.splashContent, { opacity: splashOpacity }]}>
      <Animated.View style={[styles.splashLogo, { transform: [{ scale: splashScale }] }]}>
        <Text style={styles.splashLogoText}>C</Text>
      </Animated.View>
      <Text style={styles.splashTitle}>CareerLeap</Text>
      <Text style={styles.splashSubtitle}>CAREER COMPANION</Text>
    </Animated.View>
  </SafeAreaView>;

  return <SafeAreaView style={styles.safe}>
    <StatusBar barStyle={darkMode ? "light-content" : "dark-content"} />
    <View style={styles.topbar}>
      <View style={styles.brandMark}><Text style={styles.brandMarkText}>C</Text></View>
      <View style={{flex:1}}><Text style={styles.brand}>CareerLeap</Text><Text style={styles.brandSub}>CAREER COMPANION</Text></View>
      <Pressable onPress={() => setDarkMode((v) => !v)} style={styles.themeToggle} accessibilityRole="button" accessibilityLabel={darkMode ? "Switch to light mode" : "Switch to dark mode"}><Text style={styles.themeToggleText}>{darkMode ? "☀ Light" : "☾ Dark"}</Text></Pressable>
      {user ? <Pressable hitSlop={12} onPress={() => { signOut(auth!); reset(); }}><Text style={styles.link}>Sign out</Text></Pressable> : null}
    </View>

    <KeyboardAvoidingView style={styles.keyboardArea} behavior={Platform.OS === "ios" ? "padding" : undefined}>
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
      automaticallyAdjustKeyboardInsets={Platform.OS === "ios"}
      showsVerticalScrollIndicator={false}
    >
      {!user ? <View>
        <View style={styles.hero}>
          <View style={styles.heroAccent}><View style={styles.heroAccentDot}/><Text style={styles.heroAccentText}>CAREER CLARITY STARTS HERE</Text></View>
          <Text style={styles.heroTitle}>Put your best resume forward.</Text>
          <Text style={styles.body}>Get a clear picture of your resume's strengths, understand what needs work, and apply with more confidence.</Text>
          <View style={styles.heroPills}><Text style={styles.pill}>ATS-aware insights</Text><Text style={styles.pill}>Evidence-led feedback</Text><Text style={styles.pill}>Private scans</Text></View>
        </View>
        <Card styles={styles}>
          <Text style={styles.cardTitle}>{authMode === "login" ? "Welcome back" : "Create your account"}</Text>
          <Text style={styles.bodySmall}>Sign in to access your resume analysis workspace.</Text>
          {!firebaseConfigured && <Text style={styles.warning}>Firebase setup required. Add the values from mobile/.env.example to mobile/.env.</Text>}
          <Label styles={styles}>Email address</Label><TextInput value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" placeholder="you@example.com" placeholderTextColor={C.placeholder} style={styles.input}/>
          <Label styles={styles}>Password</Label><TextInput value={password} onChangeText={setPassword} secureTextEntry autoComplete={authMode === "login" ? "current-password" : "new-password"} placeholder={authMode === "login" ? "Enter your password" : "Create a strong password"} placeholderTextColor={C.placeholder} style={styles.input}/>
          {authMode === "signup" && <Text style={styles.passwordHint}>At least 8 characters, including uppercase, lowercase, a number and a special character.</Text>}
          <Button styles={styles} C={C} title={busy ? "Please wait..." : authMode === "login" ? "Sign in" : "Create account"} onPress={handleEmailAuth} disabled={busy || !firebaseConfigured}/>
          <Pressable onPress={() => setAuthMode(authMode === "login" ? "signup" : "login")} style={styles.authSwitch}>
            <Text style={styles.linkCenter}>{authMode === "login" ? "New to CareerLeap? Create an account" : "Already have an account? Sign in"}</Text>
          </Pressable>
        </Card>
      </View> : report ? <ReportView report={report} fileName={fileName} onBack={reset} styles={styles} C={C}/> : <View>
        <View style={styles.hero}>
          <View style={styles.heroAccent}><View style={styles.heroAccentDot}/><Text style={styles.heroAccentText}>YOUR NEXT OPPORTUNITY</Text></View>
          <Text style={styles.heroTitle}>Make every application count.</Text>
          <Text style={styles.body}>Understand your resume quality and see how closely your experience aligns with the role you're targeting.</Text>
        </View>
        <Card styles={styles}>
          <View style={styles.rowBetween}><View><Text style={styles.cardTitle}>Resume analysis</Text><Text style={styles.bodySmall}>A focused review, built around evidence.</Text></View><Text style={styles.newTag}>BETA</Text></View>
          <View style={styles.uploadBox}>
            <View style={styles.uploadIconWrap}><Text style={styles.uploadIcon}>↑</Text></View>
            <Text style={styles.uploadTitle}>Upload your resume</Text>
            <Text style={styles.muted}>PDF or DOCX · Maximum 8 MB</Text>
            <Button styles={styles} C={C} title={fileName ? "Change resume" : "Choose a file"} onPress={pickResume} disabled={busy}/>
            {fileName ? <Text style={styles.selectedFile} numberOfLines={2}>Selected: {fileName}</Text> : null}
          </View>
          <View style={styles.optionalHeader}><Label styles={styles}>Target job description</Label><Text style={styles.optionalTag}>OPTIONAL</Text></View>
          <Text style={styles.bodySmall}>Choose a role to use a ready-made job description, or paste your own.</Text>
          <Pressable
            onPress={() => setShowRoleOptions((open) => !open)}
            style={styles.roleDropdown}
            accessibilityRole="button"
            accessibilityLabel="Choose a predefined job role"
          >
            <Text style={[styles.roleDropdownText, !selectedRole && styles.rolePlaceholder]}>{selectedRole || "Select a role (optional)"}</Text>
            <Text style={styles.roleDropdownChevron}>{showRoleOptions ? "▴" : "▾"}</Text>
          </Pressable>
          {showRoleOptions && <View style={styles.roleOptions}>
            {ROLE_TEMPLATES.map((role) => <Pressable
              key={role.title}
              onPress={() => {
                setJob(role.jd);
                setSelectedRole(role.title);
                setShowRoleOptions(false);
              }}
              style={styles.roleOption}
            >
              <Text style={styles.roleOptionText}>{role.title}</Text>
              {selectedRole === role.title ? <Text style={styles.roleSelected}>SELECTED</Text> : null}
            </Pressable>)}
          </View>}
          {selectedRole ? <Text style={styles.templateHint}>Using the {selectedRole} template. You can edit the job description below.</Text> : null}
          <TextInput value={job} onChangeText={setJob} multiline textAlignVertical="top" placeholder="Or paste a job description here..." placeholderTextColor={C.placeholder} style={[styles.input,styles.textarea]}/>
          <Text style={styles.bodySmall}>You can scan without a job description for a general resume-quality review, or add one for job-specific feedback.</Text>
          <Button styles={styles} C={C} title={busy ? "Scanning..." : "Scan"} onPress={scanResume} disabled={busy || !selectedAsset}/>
          {busy && <ActivityIndicator color={C.blue} style={{marginTop:14}}/>}
          <View style={styles.privacyRow}><Text style={styles.privacyIcon}>⌑</Text><Text style={styles.privacy}>Your scan isn't saved to history. The resume is processed to generate this report and is not retained by this V1 app.</Text></View>
        </Card>
        <View style={styles.sectionHeading}><Text style={styles.sectionTitle}>A clearer view of your resume</Text><Text style={styles.bodySmall}>Useful feedback, without the guesswork.</Text></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>01</Text><View style={{flex:1}}><Text style={styles.featureTitle}>Understand your score</Text><Text style={styles.bodySmall}>See the quality breakdown and optional job match.</Text></View></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>02</Text><View style={{flex:1}}><Text style={styles.featureTitle}>See the evidence</Text><Text style={styles.bodySmall}>Understand which areas need attention and why.</Text></View></View>
        <View style={styles.featureRow}><Text style={styles.featureIcon}>03</Text><View style={{flex:1}}><Text style={styles.featureTitle}>Know what to improve</Text><Text style={styles.bodySmall}>Get practical suggestions grounded in your resume.</Text></View></View>
      </View>}
      <Text style={styles.footer}>CAREERLEAP  ·  BUILT FOR YOUR NEXT STEP</Text>
    </ScrollView>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}

function Score({value, label, styles, C}: any) {
  const color = value >= 80 ? C.green : value >= 60 ? C.blue : C.amber;
  return <View style={styles.scoreCard}>
    <View style={[styles.scoreCircle,{borderColor:color}]}><Text style={[styles.scoreNumber,{color}]}>{value}</Text><Text style={styles.scoreOutOf}>/100</Text></View>
    <Text style={styles.scoreLabel}>{label}</Text>
  </View>;
}
function ReportView({report,fileName,onBack,styles,C}: any) {
  const q = report.quality;
  const j = report.job_match;
  return <View>
    <View style={styles.reportHeading}>
      <View style={styles.heroAccent}><View style={styles.heroAccentDot}/><Text style={styles.heroAccentText}>ANALYSIS COMPLETE</Text></View>
      <Text style={styles.heroTitle}>Your resume, reviewed.</Text>
      <Text style={styles.bodySmall} numberOfLines={1}>{fileName}</Text>
    </View>
    <View style={styles.scoreGrid}><Score value={q.score} label="Resume quality" styles={styles} C={C}/>{j && <Score value={j.score} label="Job match" styles={styles} C={C}/>}</View>
    <Card styles={styles}><Text style={styles.cardTitle}>Resume quality</Text><Text style={styles.bodySmall}>{q.summary}</Text>
      {q.breakdown.map((item:any) => <Breakdown key={item.key} item={item} styles={styles}/>)}
    </Card>
    {j && <Card styles={styles}><Text style={styles.cardTitle}>Job-specific match</Text><Text style={styles.bodySmall}>{j.summary}</Text>
      {j.breakdown.map((item:any) => <Breakdown key={item.key} item={item} styles={styles}/>)}
      {j.missing_skills?.length > 0 && <><Text style={styles.subhead}>Not detected in your resume</Text><View style={styles.skillWrap}>{j.missing_skills.map((s:string)=><Text key={s} style={styles.missingSkill}>{s}</Text>)}</View></>}
      {j.matched_skills?.length > 0 && <><Text style={styles.subhead}>Evidence detected</Text><View style={styles.skillWrap}>{j.matched_skills.map((s:string)=><Text key={s} style={styles.matchedSkill}>{s}</Text>)}</View></>}
    </Card>}
    {j?.actionable_suggestions?.length > 0 && <Card styles={styles}>
      <Text style={styles.cardTitle}>How to improve for this role</Text>
      <Text style={styles.bodySmall}>Specific edits based on gaps between the job description and your resume. Add a skill only if you can support it with real experience.</Text>
      {j.actionable_suggestions.map((item:any)=><View key={item.code} style={styles.actionSuggestion}>
        <View style={styles.rowBetween}><Text style={styles.findingTitle}>{item.title}</Text><Text style={[styles.priorityTag, item.priority === "high" ? styles.priorityHigh : styles.priorityMedium]}>{item.priority === "high" ? "HIGH PRIORITY" : "REVIEW"}</Text></View>
        <Text style={styles.actionLabel}>WHAT'S MISSING</Text><Text style={styles.recommendation}>{item.what_is_missing}</Text>
        <Text style={styles.actionLabel}>WHERE TO EDIT · {item.where_to_edit}</Text>
        {item.target_line ? <View style={styles.sourceLine}><Text style={styles.sourceLineLabel}>CURRENT RESUME LINE {item.target_line.line}</Text><Text style={styles.sourceLineText}>{item.target_line.text}</Text></View> : null}
        <Text style={styles.actionLabel}>SUGGESTED CHANGE</Text><Text style={styles.recommendation}>{item.suggested_change}</Text>
        <Text style={styles.actionLabel}>WORDING GUIDE</Text><Text style={styles.wordingGuide}>{item.safe_wording}</Text>
      </View>)}
    </Card>}
    {q.actionable_suggestions?.length > 0 && <Card styles={styles}>
      <Text style={styles.cardTitle}>Specific resume edits</Text>
      <Text style={styles.bodySmall}>Each suggestion points to a place in the extracted resume and gives you a safe structure to improve it.</Text>
      {q.actionable_suggestions.map((item:any)=><View key={item.code} style={styles.actionSuggestion}>
        <View style={styles.rowBetween}><Text style={styles.findingTitle}>{item.title}</Text><Text style={[styles.priorityTag, item.priority === "high" ? styles.priorityHigh : styles.priorityMedium]}>{item.priority === "low" ? "OPTIONAL" : item.priority === "high" ? "HIGH PRIORITY" : "REVIEW"}</Text></View>
        <Text style={styles.actionLabel}>WHAT'S MISSING</Text><Text style={styles.recommendation}>{item.what_is_missing}</Text>
        <Text style={styles.actionLabel}>WHERE TO EDIT · {item.where_to_edit}</Text>
        {item.target_line ? <View style={styles.sourceLine}><Text style={styles.sourceLineLabel}>REFERENCE · EXTRACTED LINE {item.target_line.line}</Text><Text style={styles.sourceLineText}>{item.target_line.text}</Text></View> : null}
        <Text style={styles.actionLabel}>SUGGESTED CHANGE</Text><Text style={styles.recommendation}>{item.suggested_change}</Text>
        <Text style={styles.actionLabel}>WORDING GUIDE</Text><Text style={styles.wordingGuide}>{item.safe_wording}</Text>
      </View>)}
    </Card>}
    <Card styles={styles}><Text style={styles.cardTitle}>Areas to strengthen</Text>
      {q.findings.length === 0 && <Text style={styles.bodySmall}>No major deductions were identified by this rubric.</Text>}
      {q.findings.map((f:any)=><Finding key={f.code} finding={f} styles={styles} C={C}/>)}
    </Card>
    {j?.findings?.length > 0 && <Card styles={styles}><Text style={styles.cardTitle}>Job match recommendations</Text>{j.findings.map((f:any)=><Finding key={f.code} finding={f} styles={styles} C={C}/>)}</Card>}
    <Card styles={styles}><Text style={styles.cardTitle}>Recommended next steps</Text>{q.top_suggestions.map((s:string,i:number)=><View key={i} style={styles.suggestion}><Text style={styles.suggestionNum}>{i+1}</Text><Text style={styles.suggestionText}>{s}</Text></View>)}</Card>
    <Text style={styles.privacy}>This score is an explainable estimate based on our V1 rubric, not a guarantee of how a particular employer's ATS will rank your resume. This scan is not saved.</Text>
    <Button styles={styles} C={C} title="Analyze another resume" onPress={onBack}/>
  </View>;
}
function Breakdown({item, styles}: any) {
  const pct = item.possible ? item.earned/item.possible : 0;
  return <View style={styles.breakdown}>
    <View style={styles.rowBetween}><Text style={styles.breakLabel}>{item.label}</Text><Text style={styles.breakValue}>{item.earned}/{item.possible}</Text></View>
    <View style={styles.barBg}><View style={[styles.barFill,{width:`${pct*100}%`} as any]}/></View>
    {item.deducted > 0 && <Text style={styles.deduction}>−{item.deducted} points</Text>}
  </View>;
}
function Finding({finding, styles, C}: any) {
  const color = finding.severity === "high" ? C.red : finding.severity === "medium" ? C.amber : C.muted;
  return <View style={styles.finding}>
    <View style={styles.rowBetween}><Text style={styles.findingTitle}>{finding.title}</Text>{finding.deduction > 0 && <Text style={[styles.deduction,{color}]}>−{finding.deduction}</Text>}</View>
    {finding.evidence && <Text style={styles.evidence}>Evidence: {finding.evidence}</Text>}
    <Text style={styles.recommendation}>{finding.recommendation}</Text>
  </View>;
}

function createStyles(C: any) { return StyleSheet.create({
  splashSafe:{flex:1,backgroundColor:C.soft},
  splashContent:{flex:1,alignItems:"center",justifyContent:"center",backgroundColor:C.soft},
  splashLogo:{width:88,height:88,borderRadius:28,backgroundColor:C.navy,alignItems:"center",justifyContent:"center",elevation:8,shadowColor:"#000000",shadowOpacity:.16,shadowRadius:18,shadowOffset:{width:0,height:8}},
  splashLogoText:{fontSize:48,fontWeight:"900",color:"#FFFFFF",letterSpacing:-2},
  splashTitle:{fontSize:26,fontWeight:"900",color:C.ink,letterSpacing:-.8,marginTop:20},
  splashSubtitle:{fontSize:10,fontWeight:"800",color:C.muted,letterSpacing:2.4,marginTop:7},
  keyboardArea:{flex:1},
  themeToggle:{paddingHorizontal:11,paddingVertical:8,borderRadius:18,backgroundColor:C.blueSoft},
  themeToggleText:{fontSize:11,fontWeight:"800",color:C.blue},
  safe:{flex:1,backgroundColor:C.soft}, center:{flex:1,alignItems:"center",justifyContent:"center"},
  topbar:{height:70,paddingHorizontal:22,flexDirection:"row",alignItems:"center",gap:12,borderBottomWidth:1,borderColor:C.line,backgroundColor:C.white},
  brandMark:{width:40,height:40,borderRadius:13,backgroundColor:C.navy,alignItems:"center",justifyContent:"center"},
  brandMarkText:{color:C.white,fontWeight:"900",fontSize:20,letterSpacing:-1},
  brand:{fontSize:17,fontWeight:"800",color:C.ink,letterSpacing:-.35},brandSub:{fontSize:9,letterSpacing:1.55,color:C.muted,marginTop:3,fontWeight:"700"},
  status:{backgroundColor:"#F2F4F7",paddingHorizontal:10,paddingVertical:6,borderRadius:20},statusText:{fontSize:11,color:C.blue,fontWeight:"700"},link:{color:C.blue,fontWeight:"700",fontSize:13},
  content:{paddingHorizontal:20,paddingTop:8,paddingBottom:42},hero:{paddingTop:22,paddingBottom:24},
  heroAccent:{flexDirection:"row",alignItems:"center",gap:7,marginBottom:12},
  heroAccentDot:{width:7,height:7,borderRadius:4,backgroundColor:C.blue},
  heroAccentText:{fontSize:10,fontWeight:"800",letterSpacing:1.5,color:C.blue},
  heroTitle:{fontSize:32,lineHeight:38,fontWeight:"800",letterSpacing:-1.05,color:C.ink,marginBottom:10},
  body:{fontSize:14,lineHeight:22,color:C.muted},bodySmall:{fontSize:12,lineHeight:18,color:C.muted,marginTop:5},
  heroPills:{flexDirection:"row",flexWrap:"wrap",gap:7,marginTop:17},
  pill:{fontSize:10,color:C.tagText,backgroundColor:C.blueSoft,paddingHorizontal:10,paddingVertical:7,borderRadius:20,fontWeight:"700"},
  card:{backgroundColor:C.white,borderRadius:20,padding:19,marginBottom:16,borderWidth:1,borderColor:C.line,elevation:2,shadowColor:"#172B4D",shadowOpacity:.045,shadowRadius:12,shadowOffset:{width:0,height:4}},
  cardTitle:{fontSize:18,fontWeight:"800",color:C.ink,letterSpacing:-.35},
  button:{backgroundColor:C.navy,paddingVertical:15,paddingHorizontal:18,borderRadius:13,alignItems:"center",marginTop:15,elevation:2,shadowColor:C.navy,shadowOpacity:.13,shadowRadius:5,shadowOffset:{width:0,height:3}},
  buttonPressed:{opacity:.86,transform:[{scale:.99}]},buttonSecondary:{backgroundColor:"#EEF1F6",elevation:0,shadowOpacity:0},buttonText:{fontSize:14,fontWeight:"800",color:C.white,letterSpacing:.1},
  separator:{flexDirection:"row",alignItems:"center",gap:10,marginVertical:19},rule:{height:1,backgroundColor:C.line,flex:1},
  muted:{fontSize:10,color:C.muted},label:{fontSize:12,fontWeight:"700",color:C.ink,marginTop:15,marginBottom:8},
  input:{borderWidth:1,borderColor:C.line,borderRadius:12,paddingHorizontal:14,paddingVertical:13,fontSize:14,color:C.ink,backgroundColor:C.input},
  authSwitch:{paddingVertical:13},linkCenter:{textAlign:"center",color:C.blue,fontSize:12,fontWeight:"700"},
  warning:{color:C.amber,fontSize:11,lineHeight:17,marginTop:12,backgroundColor:C.warningSoft,padding:10,borderRadius:9},
  passwordHint:{fontSize:10,lineHeight:16,color:C.muted,marginTop:7},
  rowBetween:{flexDirection:"row",justifyContent:"space-between",alignItems:"center"},
  newTag:{backgroundColor:C.blueSoft,color:C.blue,fontWeight:"800",fontSize:9,letterSpacing:1,paddingHorizontal:10,paddingVertical:7,borderRadius:20,overflow:"hidden"},
  uploadBox:{backgroundColor:C.panel,borderWidth:1,borderColor:"#D9E2F4",borderStyle:"dashed",borderRadius:16,padding:21,alignItems:"center",marginTop:19,marginBottom:9},
  uploadIconWrap:{width:46,height:46,borderRadius:15,backgroundColor:C.blueSoft,alignItems:"center",justifyContent:"center",marginBottom:10},
  uploadIcon:{fontSize:26,color:C.blue,fontWeight:"500",marginTop:-3},
  uploadTitle:{fontSize:15,fontWeight:"800",color:C.ink,marginBottom:5},
  selectedFile:{fontSize:11,lineHeight:17,color:C.green,fontWeight:"700",marginTop:12,textAlign:"center"},
  optionalHeader:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginTop:8},
  optionalTag:{fontSize:9,color:C.muted,letterSpacing:1,fontWeight:"800",marginTop:13},
  roleDropdown:{minHeight:48,borderWidth:1,borderColor:C.line,borderRadius:12,paddingHorizontal:14,marginTop:10,backgroundColor:C.input,flexDirection:"row",alignItems:"center",justifyContent:"space-between"},
  roleDropdownText:{fontSize:13,color:C.ink,fontWeight:"600"},rolePlaceholder:{color:C.placeholder,fontWeight:"400"},
  roleDropdownChevron:{fontSize:16,color:C.muted},
  roleOptions:{borderWidth:1,borderColor:C.line,borderRadius:12,marginTop:6,overflow:"hidden",backgroundColor:C.white},
  roleOption:{minHeight:44,paddingHorizontal:14,paddingVertical:12,borderBottomWidth:1,borderBottomColor:C.line,flexDirection:"row",alignItems:"center",justifyContent:"space-between"},
  roleOptionText:{fontSize:13,color:C.ink,fontWeight:"600"},roleSelected:{fontSize:8,color:C.blue,fontWeight:"900",letterSpacing:.7},
  templateHint:{fontSize:10,color:C.blue,marginTop:8,lineHeight:15},
  textarea:{height:116,paddingTop:13,textAlignVertical:"top",marginTop:12},
  privacyRow:{flexDirection:"row",alignItems:"flex-start",gap:8,marginTop:13},
  privacyIcon:{fontSize:17,color:C.green,fontWeight:"800",marginTop:-2},
  privacy:{flex:1,fontSize:10,lineHeight:16,color:C.muted,marginTop:12},
  sectionHeading:{marginTop:17,marginBottom:7},sectionTitle:{fontSize:18,fontWeight:"800",color:C.ink,letterSpacing:-.4},
  featureRow:{flexDirection:"row",gap:13,alignItems:"flex-start",paddingVertical:14,borderBottomWidth:1,borderBottomColor:C.line},
  featureIcon:{fontSize:11,fontWeight:"900",color:C.blue,backgroundColor:C.blueSoft,borderRadius:9,paddingHorizontal:9,paddingVertical:8,overflow:"hidden"},
  featureTitle:{fontSize:13,fontWeight:"800",color:C.ink},
  footer:{fontSize:9,letterSpacing:1.35,textAlign:"center",color:C.placeholder,marginTop:22,fontWeight:"700"},
  reportHeading:{paddingTop:20,paddingBottom:17},scoreGrid:{flexDirection:"row",gap:12,marginBottom:16},
  scoreCard:{flex:1,backgroundColor:C.white,borderRadius:18,borderWidth:1,borderColor:C.line,padding:17,alignItems:"center",elevation:1,shadowColor:"#172B4D",shadowOpacity:.04,shadowRadius:8,shadowOffset:{width:0,height:3}},
  scoreCircle:{width:96,height:96,borderRadius:48,borderWidth:5,alignItems:"center",justifyContent:"center"},
  scoreNumber:{fontSize:31,fontWeight:"900",letterSpacing:-1},scoreOutOf:{fontSize:10,color:C.muted,marginTop:-2},scoreLabel:{fontSize:12,fontWeight:"800",color:C.ink,marginTop:11},
  breakdown:{marginTop:18},breakLabel:{fontSize:12,fontWeight:"700",color:C.ink},breakValue:{fontSize:12,fontWeight:"800",color:C.ink},
  barBg:{height:8,backgroundColor:C.track,borderRadius:9,overflow:"hidden",marginTop:9},barFill:{height:8,backgroundColor:C.blue,borderRadius:9},
  deduction:{fontSize:10,color:C.red,fontWeight:"700",marginTop:5},finding:{paddingVertical:14,borderBottomWidth:1,borderBottomColor:C.line},
  findingTitle:{fontSize:13,fontWeight:"800",color:C.ink,flex:1,paddingRight:8},evidence:{fontSize:10,color:C.muted,marginTop:7,fontStyle:"italic",lineHeight:16},
  actionSuggestion:{paddingTop:16,marginTop:14,borderTopWidth:1,borderTopColor:C.line},
  actionLabel:{fontSize:9,fontWeight:"900",letterSpacing:1,color:C.blue,marginTop:13,marginBottom:4},
  sourceLine:{backgroundColor:C.panel,borderWidth:1,borderColor:C.line,borderRadius:10,padding:11,marginTop:7},
  sourceLineLabel:{fontSize:9,fontWeight:"800",color:C.muted,letterSpacing:.7,marginBottom:6},
  sourceLineText:{fontSize:11,lineHeight:17,color:C.ink},
  wordingGuide:{fontSize:11,lineHeight:18,color:C.ink,backgroundColor:C.blueSoft,padding:11,borderRadius:9,marginTop:4},
  priorityTag:{fontSize:8,fontWeight:"900",letterSpacing:.6,paddingHorizontal:7,paddingVertical:5,borderRadius:8,overflow:"hidden"},
  priorityHigh:{color:C.dangerTagText,backgroundColor:C.dangerTagBg},priorityMedium:{color:C.warningTagText,backgroundColor:C.warningTagBg},
  recommendation:{fontSize:12,lineHeight:19,color:C.body,marginTop:8},subhead:{fontSize:12,fontWeight:"800",color:C.ink,marginTop:17,marginBottom:9},
  skillWrap:{flexDirection:"row",flexWrap:"wrap",gap:7},
  missingSkill:{fontSize:10,color:C.dangerTagText,backgroundColor:C.dangerTagBg,paddingHorizontal:10,paddingVertical:7,borderRadius:20,overflow:"hidden",fontWeight:"600"},
  matchedSkill:{fontSize:10,color:C.successTagText,backgroundColor:C.successTagBg,paddingHorizontal:10,paddingVertical:7,borderRadius:20,overflow:"hidden",fontWeight:"600"},
  suggestion:{flexDirection:"row",gap:11,marginTop:15,alignItems:"flex-start"},
  suggestionNum:{width:24,height:24,textAlign:"center",textAlignVertical:"center",borderRadius:12,overflow:"hidden",backgroundColor:C.blueSoft,color:C.blue,fontWeight:"900",fontSize:11},
  suggestionText:{flex:1,fontSize:12,lineHeight:19,color:C.body},
}); }

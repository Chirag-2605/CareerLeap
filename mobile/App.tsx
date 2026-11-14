import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator, Animated, AppState, KeyboardAvoidingView, Platform, Pressable, SafeAreaView,
  ScrollView, StatusBar, StyleSheet, Text, TextInput, View
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import {
  createUserWithEmailAndPassword, onAuthStateChanged, reload, sendEmailVerification,
  signInWithEmailAndPassword, signOut, User
} from "firebase/auth";
import { auth, firebaseConfigured } from "./src/firebase";
import { analyzeResume } from "./src/api";
import { DARK_THEME, LIGHT_THEME } from "./src/theme";


// Firebase refresh tokens can keep a user signed in indefinitely. Enforce a fixed 24-hour session lifetime using the original authentication timestamp.
const SESSION_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const PASSWORD_RULE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9\s]).{8,}$/;
const EMAIL_LOCAL_RE = /^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+$/i;
const EMAIL_LABEL_RE = /^[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?$/i;

type Report = any;
type ToastTone = "success" | "error" | "info";
function isValidEmail(value: string) {
  const email = value.trim();
  if (!email || email.length > 254 || email.includes("..")) return false;
  const parts = email.split("@");
  if (parts.length !== 2) return false;
  const [local, domain] = parts;
  if (!local || local.length > 64 || !EMAIL_LOCAL_RE.test(local) || local.startsWith(".") || local.endsWith(".")) return false;
  const labels = domain.split(".");
  return labels.length >= 2 && labels.every(label => label.length > 0 && label.length <= 63 && EMAIL_LABEL_RE.test(label))
    && /^[A-Z]{2,63}$/i.test(labels[labels.length - 1]);
}
function firebaseAuthMessage(error: any) {
  const code = error?.code || "";
  if (code.includes("CONFIGURATION_NOT_FOUND") || code === "auth/operation-not-allowed") return "Email sign-in is not enabled yet. Please contact support.";
  if (code === "auth/invalid-api-key" || code === "auth/api-key-not-valid") return "Authentication is temporarily unavailable. Please try again later.";
  if (code === "auth/network-request-failed") return "Couldn't reach the sign-in service. Check your internet connection.";
  if (code === "auth/invalid-email") return "Enter a valid email address.";
  if (code === "auth/email-already-in-use") return "An account with this email already exists. Try signing in.";
  if (code === "auth/invalid-credential" || code === "auth/wrong-password" || code === "auth/user-not-found") return "Incorrect email or password.";
  if (code === "auth/weak-password") return "Choose a stronger password.";
  if (code === "auth/too-many-requests") return "Too many attempts. Please wait a moment and try again.";
  if (code === "auth/user-disabled") return "This account is disabled. Please contact support.";
  return "Authentication couldn't be completed. Please try again.";
}

const SCAN_STEPS = [
  "Uploading your resume securely",
  "Extracting text and resume sections",
  "Reviewing skills and experience",
  "Preparing your personalized suggestions",
];

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
  const [showPassword, setShowPassword] = useState(false);
  const [authMode, setAuthMode] = useState<"login"|"signup">("login");
  const [toast, setToast] = useState<{message:string; tone:ToastTone}|null>(null);
  const [loadingMode, setLoadingMode] = useState<"auth"|"scan"|null>(null);
  const [scanStage, setScanStage] = useState(0);
  const [job, setJob] = useState("");
  const [selectedRole, setSelectedRole] = useState("");
  const [showRoleOptions, setShowRoleOptions] = useState(false);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Report|null>(null);
  const [fileName, setFileName] = useState("");
  const [selectedAsset, setSelectedAsset] = useState<DocumentPicker.DocumentPickerAsset | null>(null);
  const [showScanner, setShowScanner] = useState(false);

  const sessionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const authFlowInProgress = useRef(false);
  const showToast = (message: string, tone: ToastTone = "info") => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({message, tone});
    toastTimer.current = setTimeout(() => setToast(null), 3600);
  };

  useEffect(() => () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
  }, []);

  useEffect(() => {
    if (loadingMode !== "scan") {
      setScanStage(0);
      return;
    }
    const timer = setInterval(() => setScanStage(current => Math.min(current + 1, SCAN_STEPS.length - 1)), 1500);
    return () => clearInterval(timer);
  }, [loadingMode]);

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
      if (checking || !mounted || authFlowInProgress.current || firebaseAuth.currentUser?.uid !== candidate.uid) return;
      checking = true;
      try {
        await reload(candidate);
        if (!candidate.emailVerified) {
          clearSessionTimer();
          if (mounted) {
            setUser(null);
            showToast("Please verify your email address before continuing. Check your inbox for the verification link.", "info");
          }
          if (firebaseAuth.currentUser?.uid === candidate.uid) await signOut(firebaseAuth);
          return;
        }
        const token = await candidate.getIdTokenResult(true);
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
        if (mounted) {
          setUser(null);
          showToast("We couldn't verify your session. Please sign in again.", "error");
        }
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
    if (!auth) return showToast("Firebase setup is incomplete. Please try again later.", "error");
    const normalizedEmail = email.trim();
    if (!isValidEmail(normalizedEmail)) return showToast("Enter a valid email address, such as name@example.com.", "error");
    if (authMode === "signup" && !PASSWORD_RULE.test(password)) {
      return showToast("Use at least 8 characters with uppercase, lowercase, a number and a special character.", "error");
    }
    if (!password) return showToast("Enter your password.", "error");

    authFlowInProgress.current = true;
    setBusy(true);
    setLoadingMode("auth");
    try {
      if (authMode === "signup") {
        const credential = await createUserWithEmailAndPassword(auth, normalizedEmail, password);
        await sendEmailVerification(credential.user);
        await signOut(auth);
        setUser(null);
        setPassword("");
        setAuthMode("login");
        setShowPassword(false);
        showToast("Verification link sent. Verify your email before signing in.", "success");
      } else {
        const credential = await signInWithEmailAndPassword(auth, normalizedEmail, password);
        await reload(credential.user);
        if (!credential.user.emailVerified) {
          await sendEmailVerification(credential.user);
          await signOut(auth);
          setUser(null);
          setPassword("");
          showToast("Your email isn't verified yet. We've sent a fresh verification link.", "info");
          return;
        }
        await credential.user.getIdToken(true);
        setUser(credential.user);
        setPassword("");
        showToast("Signed in successfully.", "success");
      }
    } catch (e:any) {
      showToast(firebaseAuthMessage(e), "error");
    } finally {
      authFlowInProgress.current = false;
      setBusy(false);
      setLoadingMode(null);
    }
  };

  const pickResume = async () => {
    if (!user) return showToast("Please sign in before scanning.", "error");
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
    } catch {
      showToast("Couldn't select that file. Please try again.", "error");
    }
  };

  const scanResume = async () => {
    if (!user) return showToast("Please sign in before scanning.", "error");
    if (!selectedAsset) return showToast("Select a PDF or DOCX before scanning.", "error");
    setBusy(true);
    setLoadingMode("scan");
    setScanStage(0);
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
      showToast(e?.message || "Resume analysis couldn't be completed. Please try again.", "error");
    } finally {
      setBusy(false);
      setLoadingMode(null);
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
    <StatusBar barStyle={darkMode ? "light-content" : "dark-content"}/>
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
      {user ? <Pressable hitSlop={12} onPress={() => { void signOut(auth!).then(() => { reset(); showToast("Signed out.", "success"); }).catch(() => showToast("Couldn't sign out. Please try again.", "error")); }}><Text style={styles.link}>Sign out</Text></Pressable> : null}
    </View>
    {toast && <View pointerEvents="none" style={[styles.toast, toast.tone === "error" ? styles.toastError : toast.tone === "success" ? styles.toastSuccess : styles.toastInfo]}>
      <Text style={styles.toastIcon}>{toast.tone === "error" ? "!" : toast.tone === "success" ? "✓" : "i"}</Text>
      <Text style={styles.toastText}>{toast.message}</Text>
    </View>}

    <KeyboardAvoidingView style={styles.keyboardArea} behavior={Platform.OS === "ios" ? "padding" : "height"}>
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
          <Label styles={styles}>Password</Label>
          <View style={styles.passwordRow}>
            <TextInput value={password} onChangeText={setPassword} secureTextEntry={!showPassword} autoComplete={authMode === "login" ? "current-password" : "new-password"} placeholder={authMode === "login" ? "Enter your password" : "Create a strong password"} placeholderTextColor={C.placeholder} style={[styles.input,styles.passwordInput]}/>
            <Pressable onPress={() => setShowPassword(value => !value)} style={styles.passwordToggle} accessibilityRole="button" accessibilityLabel={showPassword ? "Hide password" : "Show password"}>
              <Text style={styles.passwordToggleText}>{showPassword ? "Hide" : "Show"}</Text>
            </Pressable>
          </View>
          {authMode === "signup" && <Text style={styles.passwordHint}>At least 8 characters, including uppercase, lowercase, a number and a special character.</Text>}
          <Button styles={styles} C={C} title={busy ? "Please wait..." : authMode === "login" ? "Sign in" : "Create account"} onPress={handleEmailAuth} disabled={busy || !firebaseConfigured}/>
          {loadingMode === "auth" && <View style={styles.authLoading}><ActivityIndicator size="small" color={C.blue}/><Text style={styles.bodySmall}>Securely checking your account…</Text></View>}
          <Pressable onPress={() => { setAuthMode(authMode === "login" ? "signup" : "login"); setShowPassword(false); }} style={styles.authSwitch}>
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
          {loadingMode === "scan" && <View style={styles.scanProgress}>
            <View style={styles.progressHeader}><ActivityIndicator color={C.blue}/><Text style={styles.progressTitle}>Analyzing your resume</Text></View>
            <View style={styles.progressTrack}><View style={[styles.progressFill,{width:Math.min(90,(scanStage + 1) * 22.5) + "%"}]}/></View>
            {SCAN_STEPS.map((step,index) => <View key={step} style={styles.scanStep}>
              <Text style={[styles.scanStepMark,index < scanStage && {color:C.green}]}>{index < scanStage ? "✓" : index === scanStage ? "●" : "○"}</Text>
              <Text style={[styles.scanStepText,index === scanStage && {color:C.ink,fontWeight:"700"}]}>{step}</Text>
              <Text style={styles.scanStepStatus}>{index < scanStage ? "Done" : index === scanStage ? "Now" : "Next"}</Text>
            </View>)}
            <Text style={styles.progressNote}>These are illustrative stages. Your report appears when the actual analysis finishes.</Text>
          </View>}
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
  const assessed = typeof value === "number" && Number.isFinite(value);
  const color = !assessed ? C.muted : value >= 80 ? C.green : value >= 60 ? C.blue : C.amber;
  return <View style={styles.scoreCard}>
    <View style={[styles.scoreCircle,{borderColor:color}]}><Text style={[styles.scoreNumber,{color}]}>{assessed ? value : "N/A"}</Text>{assessed && <Text style={styles.scoreOutOf}>/100</Text>}</View>
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
    {q.suggestion_design?.items?.length > 0 ? <Card styles={styles}>
      <Text style={styles.cardTitle}>Your improvement plan</Text>
      <Text style={styles.bodySmall}>Prioritized edits designed after the resume and job-match analysis. Start with the highest-impact evidence gaps; optional polish comes last.</Text>
      {q.suggestion_design.items.map((item:any)=><View key={item.code} style={styles.actionSuggestion}>
        <View style={styles.rowBetween}>
          <Text style={styles.findingTitle}>{item.title}</Text>
          <Text style={[styles.priorityTag, item.priority === "high" ? styles.priorityHigh : styles.priorityMedium]}>{item.priority === "high" ? "HIGH PRIORITY" : item.priority === "low" ? "OPTIONAL" : "REVIEW"}</Text>
        </View>
        <Text style={styles.actionLabel}>{String(item.category || "suggestion").replace(/_/g," ").toUpperCase()} · WHY IT MATTERS</Text>
        <Text style={styles.recommendation}>{item.why_it_matters}</Text>
        <Text style={styles.actionLabel}>WHERE TO EDIT · {item.where_to_edit}</Text>
        {item.source_line ? <View style={styles.sourceLine}><Text style={styles.sourceLineLabel}>SOURCE · EXTRACTED LINE {item.source_line.line}</Text><Text style={styles.sourceLineText}>{item.source_line.text}</Text></View> : null}
        {item.questions_to_answer?.length > 0 ? <>
          <Text style={styles.actionLabel}>DETAILS TO ADD</Text>
          {item.questions_to_answer.map((question:string,index:number)=><Text key={index} style={styles.recommendation}>• {question}</Text>)}
        </> : null}
        {item.rewrite_template ? <><Text style={styles.actionLabel}>SAFE REWRITE STRUCTURE</Text><Text style={styles.rewriteText}>{item.rewrite_template}</Text></> : null}
        {item.impact_guidance ? <><Text style={styles.actionLabel}>IMPACT GUIDANCE</Text><Text style={styles.wordingGuide}>{item.impact_guidance}</Text></> : null}
        <Text style={styles.wordingGuide}>{item.safety_note}</Text>
      </View>)}
    </Card> : <>
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
          <View style={styles.rowBetween}><Text style={styles.findingTitle}>{item.title}</Text><Text style={[styles.priorityTag, item.priority === "low" ? styles.priorityMedium : item.priority === "high" ? styles.priorityHigh : styles.priorityMedium]}>{item.priority === "low" ? "OPTIONAL" : item.priority === "high" ? "HIGH PRIORITY" : "REVIEW"}</Text></View>
          <Text style={styles.actionLabel}>WHAT'S MISSING</Text><Text style={styles.recommendation}>{item.what_is_missing}</Text>
          <Text style={styles.actionLabel}>WHERE TO EDIT · {item.where_to_edit}</Text>
          {item.target_line ? <View style={styles.sourceLine}><Text style={styles.sourceLineLabel}>REFERENCE · EXTRACTED LINE {item.target_line.line}</Text><Text style={styles.sourceLineText}>{item.target_line.text}</Text></View> : null}
          <Text style={styles.actionLabel}>SUGGESTED CHANGE</Text><Text style={styles.recommendation}>{item.suggested_change}</Text>
          {item.suggested_rewrite ? <><Text style={styles.actionLabel}>SUGGESTED REWRITE</Text><Text style={styles.rewriteText}>{item.suggested_rewrite}</Text></> : null}
          <Text style={styles.actionLabel}>WORDING GUIDE</Text><Text style={styles.wordingGuide}>{item.safe_wording}</Text>
        </View>)}
      </Card>}
    </>}
    <Card styles={styles}><Text style={styles.cardTitle}>Areas to strengthen</Text>
      {q.findings.length === 0 && <Text style={styles.bodySmall}>No major deductions were identified by this rubric.</Text>}
      {q.findings.map((f:any)=><Finding key={f.code} finding={f} styles={styles} C={C}/>)}
    </Card>
    {j?.findings?.length > 0 && <Card styles={styles}><Text style={styles.cardTitle}>Job match recommendations</Text>{j.findings.map((f:any)=><Finding key={f.code} finding={f} styles={styles} C={C}/>)}</Card>}
    <Card styles={styles}><Text style={styles.cardTitle}>Recommended next steps</Text>{q.top_suggestions.map((s:string,i:number)=><View key={i} style={styles.suggestion}><Text style={styles.suggestionNum}>{i+1}</Text><Text style={styles.suggestionText}>{s}</Text></View>)}</Card>
    <Text style={styles.privacy}>This score is an explainable estimate from CareerLeap's deterministic rubric, not a guarantee of how a particular employer's ATS will rank your resume. This scan is not saved.</Text>
    <Button styles={styles} C={C} title="Analyze another resume" onPress={onBack}/>
  </View>;
}
function Breakdown({item, styles}: any) {
  const assessed = typeof item.earned === "number" && Number.isFinite(item.earned);
  const pct = item.possible && assessed ? item.earned/item.possible : 0;
  return <View style={styles.breakdown}>
    <View style={styles.rowBetween}><Text style={styles.breakLabel}>{item.label}</Text><Text style={styles.breakValue}>{assessed ? `${item.earned}/${item.possible}` : "Not assessed"}</Text></View>
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
  splashSafe:{flex:1,backgroundColor:C.soft,paddingTop:Platform.OS === "android" ? (StatusBar.currentHeight || 0) : 0},
  splashContent:{flex:1,alignItems:"center",justifyContent:"center",backgroundColor:C.soft},
  splashLogo:{width:88,height:88,borderRadius:28,backgroundColor:C.navy,alignItems:"center",justifyContent:"center",elevation:8,shadowColor:"#000000",shadowOpacity:.16,shadowRadius:18,shadowOffset:{width:0,height:8}},
  splashLogoText:{fontSize:48,fontWeight:"900",color:"#FFFFFF",letterSpacing:-2},
  splashTitle:{fontSize:26,fontWeight:"900",color:C.ink,letterSpacing:-.8,marginTop:20},
  splashSubtitle:{fontSize:10,fontWeight:"800",color:C.muted,letterSpacing:2.4,marginTop:7},
  keyboardArea:{flex:1},
  themeToggle:{paddingHorizontal:11,paddingVertical:8,borderRadius:18,backgroundColor:C.blueSoft},
  themeToggleText:{fontSize:11,fontWeight:"800",color:C.blue},
  safe:{flex:1,backgroundColor:C.soft,paddingTop:Platform.OS === "android" ? (StatusBar.currentHeight || 0) : 0}, center:{flex:1,alignItems:"center",justifyContent:"center"},
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
  passwordRow:{flexDirection:"row",alignItems:"center",position:"relative"},
  passwordInput:{flex:1,paddingRight:66},
  passwordToggle:{position:"absolute",right:12,paddingHorizontal:5,paddingVertical:9},
  passwordToggleText:{fontSize:12,fontWeight:"800",color:C.blue},
  toast:{position:"absolute",top:78,left:18,right:18,zIndex:1000,elevation:12,borderRadius:14,paddingHorizontal:14,paddingVertical:13,flexDirection:"row",alignItems:"center",gap:10,borderWidth:1,borderColor:C.line,backgroundColor:C.white},
  toastError:{borderLeftWidth:4,borderLeftColor:C.red},toastSuccess:{borderLeftWidth:4,borderLeftColor:C.green},toastInfo:{borderLeftWidth:4,borderLeftColor:C.blue},
  toastIcon:{fontSize:14,fontWeight:"900",color:C.blue,width:18,textAlign:"center"},
  toastText:{flex:1,fontSize:12,lineHeight:18,color:C.ink,fontWeight:"600"},
  authLoading:{flexDirection:"row",alignItems:"center",justifyContent:"center",gap:9,marginTop:12},
  scanProgress:{marginTop:16,padding:14,borderRadius:14,backgroundColor:C.panel,borderWidth:1,borderColor:C.line},
  progressHeader:{flexDirection:"row",alignItems:"center",gap:9},
  progressTitle:{fontSize:13,fontWeight:"800",color:C.ink},
  progressTrack:{height:7,backgroundColor:C.track,borderRadius:8,overflow:"hidden",marginTop:14,marginBottom:8},
  progressFill:{height:7,backgroundColor:C.blue,borderRadius:8},
  scanStep:{flexDirection:"row",alignItems:"center",gap:8,paddingVertical:7},
  scanStepMark:{width:15,fontSize:12,color:C.muted,fontWeight:"900"},
  scanStepText:{flex:1,fontSize:11,color:C.muted},
  scanStepStatus:{fontSize:9,color:C.muted,fontWeight:"700"},
  progressNote:{fontSize:9,lineHeight:14,color:C.muted,marginTop:7},
  rewriteText:{fontSize:12,lineHeight:19,color:C.ink,backgroundColor:C.blueSoft,padding:11,borderRadius:9,marginTop:4},
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

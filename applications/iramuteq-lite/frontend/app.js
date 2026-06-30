import { closeParameterDialogs, createProgressionController } from "./progression.js";

const corpusFileInput = document.getElementById("corpusFile");
const importCorpusBtn = document.getElementById("importCorpusBtn");
const downloadResultsBtn = document.getElementById("downloadResultsBtn");
const fileInfo = document.getElementById("fileInfo");
const downloadResultsStatus = document.getElementById("downloadResultsStatus");
const analysisHistory = document.getElementById("analysisHistory");
const sidebarStatus = document.getElementById("sidebarStatus");
const sidebarStatusPill = document.querySelector(".status-pill");
const sidebarStatusDot = document.querySelector(".status-dot");
const releaseAccessBtn = document.getElementById("releaseAccessBtn");
const sidebarRuntimeStatus = document.getElementById("sidebarRuntimeStatus");
const progress = document.getElementById("progress");
const progressLabel = document.getElementById("progressLabel");
const runProgressDialog = document.getElementById("runProgressDialog");
const runProgressTitle = document.getElementById("runProgressTitle");
const runProgressMessage = document.getElementById("runProgressMessage");
const runProgressBar = document.getElementById("runProgressBar");
const runProgressValue = document.getElementById("runProgressValue");
const startupBootstrapDialog = document.getElementById("startupBootstrapDialog");
const startupBootstrapTitle = document.getElementById("startupBootstrapTitle");
const startupBootstrapMessage = document.getElementById("startupBootstrapMessage");
const startupBootstrapBar = document.getElementById("startupBootstrapBar");
const startupBootstrapValue = document.getElementById("startupBootstrapValue");
const imagePreviewDialog = document.getElementById("imagePreviewDialog");
const imagePreviewKicker = document.getElementById("imagePreviewKicker");
const imagePreviewTitle = document.getElementById("imagePreviewTitle");
const imagePreviewContent = document.getElementById("imagePreviewContent");
const imagePreviewCounter = document.getElementById("imagePreviewCounter");
const imagePreviewPrevBtn = document.getElementById("imagePreviewPrevBtn");
const imagePreviewNextBtn = document.getElementById("imagePreviewNextBtn");
const closeImagePreviewBtn = document.getElementById("closeImagePreviewBtn");
const multimodalFaceSelectionDialog = document.getElementById("multimodalFaceSelectionDialog");
const multimodalFaceSelectionStage = document.getElementById("multimodalFaceSelectionStage");
const multimodalFaceSelectionCoords = document.getElementById("multimodalFaceSelectionCoords");
const multimodalFaceSelectionSource = document.getElementById("multimodalFaceSelectionSource");
const closeMultimodalFaceSelectionBtn = document.getElementById("closeMultimodalFaceSelectionBtn");
const resetMultimodalFaceSelectionBtn = document.getElementById("resetMultimodalFaceSelectionBtn");
const saveMultimodalFaceSelectionBtn = document.getElementById("saveMultimodalFaceSelectionBtn");
const chdTermContextMenu = document.getElementById("chdTermContextMenu");
const termSegmentsDialog = document.getElementById("termSegmentsDialog");
const termSegmentsKicker = document.getElementById("termSegmentsKicker");
const termSegmentsTitle = document.getElementById("termSegmentsTitle");
const termSegmentsMeta = document.getElementById("termSegmentsMeta");
const termSegmentsList = document.getElementById("termSegmentsList");
const termSegmentsFooter = document.getElementById("termSegmentsFooter");
const termSegmentsStatus = document.getElementById("termSegmentsStatus");
const saveChi2PngBtn = document.getElementById("saveChi2PngBtn");
const buildSubcorpusBtn = document.getElementById("buildSubcorpusBtn");
const closeTermSegmentsBtn = document.getElementById("closeTermSegmentsBtn");
const logs = document.getElementById("logs");
const corpusPreview = document.getElementById("corpusPreview");
const analysisSteps = document.getElementById("analysisSteps");
const analysisSummary = document.getElementById("analysisSummary");
const zipfChart = document.getElementById("zipfChart");
const chdDendrogramSelect = document.getElementById("chdDendrogramSelect");
const chdConfigDialog = document.getElementById("chdConfigDialog");
const chdConfigDialogContent = document.getElementById("chdConfigDialogContent");
const closeChdDialogBtn = document.getElementById("closeChdDialogBtn");
const launchChdDialogBtn = document.getElementById("launchChdDialogBtn");
const simiConfigDialog = document.getElementById("simiConfigDialog");
const simiConfigDialogContent = document.getElementById("simiConfigDialogContent");
const closeSimiDialogBtn = document.getElementById("closeSimiDialogBtn");
const launchSimiDialogBtn = document.getElementById("launchSimiDialogBtn");
const ldaConfigDialog = document.getElementById("ldaConfigDialog");
const ldaConfigDialogContent = document.getElementById("ldaConfigDialogContent");
const closeLdaDialogBtn = document.getElementById("closeLdaDialogBtn");
const launchLdaDialogBtn = document.getElementById("launchLdaDialogBtn");
const suiviConfigDialog = document.getElementById("suiviConfigDialog");
const suiviConfigDialogContent = document.getElementById("suiviConfigDialogContent");
const closeSuiviDialogBtn = document.getElementById("closeSuiviDialogBtn");
const launchSuiviDialogBtn = document.getElementById("launchSuiviDialogBtn");
const multimodalCompareAbConfigDialog = document.getElementById("multimodalCompareAbConfigDialog");
const multimodalCompareAbConfigDialogContent = document.getElementById("multimodalCompareAbConfigDialogContent");
const closeMultimodalCompareAbDialogBtn = document.getElementById("closeMultimodalCompareAbDialogBtn");
const applyMultimodalCompareAbDialogBtn = document.getElementById("applyMultimodalCompareAbDialogBtn");
const afcTermsZoomInBtn = document.getElementById("afcTermsZoomInBtn");
const afcTermsZoomOutBtn = document.getElementById("afcTermsZoomOutBtn");
const afcTermsZoomResetBtn = document.getElementById("afcTermsZoomResetBtn");
const simiZoomInBtn = document.getElementById("simiZoomInBtn");
const simiZoomOutBtn = document.getElementById("simiZoomOutBtn");
const simiZoomResetBtn = document.getElementById("simiZoomResetBtn");
const simiZoomValue = document.getElementById("simiZoomValue");
const annotationImportBtn = document.getElementById("annotationImportBtn");
const annotationImportCsv = document.getElementById("annotationImportCsv");
const annotationDownloadCsvBtn = document.getElementById("annotationDownloadCsvBtn");
const annotationCorpusText = document.getElementById("annotationCorpusText");
const annotationCorpusColored = document.getElementById("annotationCorpusColored");
const annotationSelection = document.getElementById("annotationSelection");
const annotationNorm = document.getElementById("annotationNorm");
const annotationMorpho = document.getElementById("annotationMorpho");
const annotationAddEntryBtn = document.getElementById("annotationAddEntryBtn");
const annotationRemoveKey = document.getElementById("annotationRemoveKey");
const annotationRemoveEntryBtn = document.getElementById("annotationRemoveEntryBtn");
const annotationDictTable = document.getElementById("annotationDictTable");
const annotationSaveStatus = document.getElementById("annotationSaveStatus");
const helpMarkdownContent = document.getElementById("helpMarkdownContent");
const helpMorphoMarkdownContent = document.getElementById("helpMorphoMarkdownContent");
const helpLdaMarkdownContent = document.getElementById("helpLdaMarkdownContent");
const helpJsdMarkdownContent = document.getElementById("helpJsdMarkdownContent");
const helpSuiviMarkdownContent = document.getElementById("helpSuiviMarkdownContent");
const helpMultimodaleMarkdownContent = document.getElementById("helpMultimodaleMarkdownContent");
const multimodalYoutubeUrl = document.getElementById("multimodalYoutubeUrl");
const multimodalPickCookiesBtn = document.getElementById("multimodalPickCookiesBtn");
const multimodalCookiesFile = document.getElementById("multimodalCookiesFile");
const multimodalYoutubeStatus = document.getElementById("multimodalYoutubeStatus");
const multimodalCookiesStatus = document.getElementById("multimodalCookiesStatus");
const multimodalYoutubePreview = document.getElementById("multimodalYoutubePreview");
const multimodalPickAudioBtn = document.getElementById("multimodalPickAudioBtn");
const multimodalAudioFile = document.getElementById("multimodalAudioFile");
const multimodalAudioStatus = document.getElementById("multimodalAudioStatus");
const multimodalPickVideoBtn = document.getElementById("multimodalPickVideoBtn");
const multimodalVideoFile = document.getElementById("multimodalVideoFile");
const multimodalVideoStatus = document.getElementById("multimodalVideoStatus");
const multimodalPickOutputDirBtn = document.getElementById("multimodalPickOutputDirBtn");
const multimodalOutputDirStatus = document.getElementById("multimodalOutputDirStatus");
const multimodalExtractMp4 = document.getElementById("multimodalExtractMp4");
const multimodalExtractMp3 = document.getElementById("multimodalExtractMp3");
const multimodalExtractWav = document.getElementById("multimodalExtractWav");
const multimodalExtractSegments = document.getElementById("multimodalExtractSegments");
const multimodalExtractImages = document.getElementById("multimodalExtractImages");
const multimodalFrameRate1 = document.getElementById("multimodalFrameRate1");
const multimodalFrameRate25 = document.getElementById("multimodalFrameRate25");
const multimodalIntervalMode = document.getElementById("multimodalIntervalMode");
const multimodalExtractStartHours = document.getElementById("multimodalExtractStartHours");
const multimodalExtractStartMinutes = document.getElementById("multimodalExtractStartMinutes");
const multimodalExtractStartSeconds = document.getElementById("multimodalExtractStartSeconds");
const multimodalExtractEndHours = document.getElementById("multimodalExtractEndHours");
const multimodalExtractEndMinutes = document.getElementById("multimodalExtractEndMinutes");
const multimodalExtractEndSeconds = document.getElementById("multimodalExtractEndSeconds");
const multimodalFrameQualityLow = document.getElementById("multimodalFrameQualityLow");
const multimodalFrameQualityHigh = document.getElementById("multimodalFrameQualityHigh");
const multimodalExtractStatus = document.getElementById("multimodalExtractStatus");
const multimodalYtdlpRunStatus = document.getElementById("multimodalYtdlpRunStatus");
const multimodalAudioImportShortcutBtn = document.getElementById("multimodalAudioImportShortcutBtn");
const multimodalAudioAmplitudeFilterK = document.getElementById("multimodalAudioAmplitudeFilterK");
const multimodalAudioRunStatus = document.getElementById("multimodalAudioRunStatus");
const multimodalAudioPausesPlot = document.getElementById("multimodalAudioPausesPlot");
const multimodalAudioSpeechRatePlot = document.getElementById("multimodalAudioSpeechRatePlot");
const multimodalAudioAnomaliesPlot = document.getElementById("multimodalAudioAnomaliesPlot");
const multimodalAudioAnomaliesConcordancier = document.getElementById("multimodalAudioAnomaliesConcordancier");
const multimodalAudioTable = document.getElementById("multimodalAudioTable");
const multimodalImagesImportShortcutBtn = document.getElementById("multimodalImagesImportShortcutBtn");
const multimodalImagesFiles = document.getElementById("multimodalImagesFiles");
const multimodalImagesStatus = document.getElementById("multimodalImagesStatus");
const multimodalImagesGallery = document.getElementById("multimodalImagesGallery");
const multimodalMotionRunStatus = document.getElementById("multimodalMotionRunStatus");
const multimodalMotionTimelinePlot = document.getElementById("multimodalMotionTimelinePlot");
const multimodalMotionRawGallery = document.getElementById("multimodalMotionRawGallery");
const multimodalMotionMagnitudeGallery = document.getElementById("multimodalMotionMagnitudeGallery");
const multimodalMotionEntropyGallery = document.getElementById("multimodalMotionEntropyGallery");
const multimodalMotionHsvGallery = document.getElementById("multimodalMotionHsvGallery");
const multimodalMotionVectorsGallery = document.getElementById("multimodalMotionVectorsGallery");
const multimodalMotionOverlayGallery = document.getElementById("multimodalMotionOverlayGallery");
const multimodalMotionAnatomyGallery = document.getElementById("multimodalMotionAnatomyGallery");
const multimodalMotionWindowsTable = document.getElementById("multimodalMotionWindowsTable");
const multimodalMotionFramesTable = document.getElementById("multimodalMotionFramesTable");
const multimodalMotionAnatomyBackend = document.getElementById("multimodalMotionAnatomyBackend");
const multimodalMotionAnatomyMode = document.getElementById("multimodalMotionAnatomyMode");
const multimodalMotionFaceAnalysisMode = document.getElementById("multimodalMotionFaceAnalysisMode");
const multimodalSelectFaceBtn = document.getElementById("multimodalSelectFaceBtn");
const multimodalClearFaceSelectionBtn = document.getElementById("multimodalClearFaceSelectionBtn");
const multimodalFaceSelectionStatus = document.getElementById("multimodalFaceSelectionStatus");
const multimodalFramesRunStatus = document.getElementById("multimodalFramesRunStatus");
const multimodalPickSegmentsBtn = document.getElementById("multimodalPickSegmentsBtn");
const multimodalSegmentsFile = document.getElementById("multimodalSegmentsFile");
const multimodalSegmentsStatus = document.getElementById("multimodalSegmentsStatus");
const multimodalAlignAudioShortcutBtn = document.getElementById("multimodalAlignAudioShortcutBtn");
const multimodalAlignImageShortcutBtn = document.getElementById("multimodalAlignImageShortcutBtn");
const multimodalAlignOverlayImages = document.getElementById("multimodalAlignOverlayImages");
const multimodalAlignOverlaySegments = document.getElementById("multimodalAlignOverlaySegments");
const multimodalAlignOverlayAudio = document.getElementById("multimodalAlignOverlayAudio");
const multimodalAlignImageView = document.getElementById("multimodalAlignImageView");
const multimodalAlignTimelineScale = document.getElementById("multimodalAlignTimelineScale");
const multimodalAlignCurveMode = document.getElementById("multimodalAlignCurveMode");
const multimodalAlignOverlayStatus = document.getElementById("multimodalAlignOverlayStatus");
const multimodalAlignRunStatus = document.getElementById("multimodalAlignRunStatus");
const multimodalAlignSourcesStatus = document.getElementById("multimodalAlignSourcesStatus");
const multimodalAlignPreview = document.getElementById("multimodalAlignPreview");
const runMultimodalNodesBtn = document.getElementById("runMultimodalNodesBtn");
const multimodalNodesRunStatus = document.getElementById("multimodalNodesRunStatus");
const multimodalNodesSourcesStatus = document.getElementById("multimodalNodesSourcesStatus");
const multimodalNodesEventMode = document.getElementById("multimodalNodesEventMode");
const multimodalNodesEntropyK = document.getElementById("multimodalNodesEntropyK");
const multimodalNodesSummary = document.getElementById("multimodalNodesSummary");
const multimodalNodesGraph = document.getElementById("multimodalNodesGraph");
const multimodalNodesDetail = document.getElementById("multimodalNodesDetail");
const multimodalNodesTable = document.getElementById("multimodalNodesTable");
const multimodalEdgesTable = document.getElementById("multimodalEdgesTable");
const multimodalCompareYoutubeUrlA = document.getElementById("multimodalCompareYoutubeUrlA");
const multimodalCompareYoutubeUrlB = document.getElementById("multimodalCompareYoutubeUrlB");
const multimodalComparePickVideoABtn = document.getElementById("multimodalComparePickVideoABtn");
const multimodalComparePickVideoBBtn = document.getElementById("multimodalComparePickVideoBBtn");
const multimodalCompareSelectFaceABtn = document.getElementById("multimodalCompareSelectFaceABtn");
const multimodalCompareSelectFaceBBtn = document.getElementById("multimodalCompareSelectFaceBBtn");
const multimodalCompareClearFaceABtn = document.getElementById("multimodalCompareClearFaceABtn");
const multimodalCompareClearFaceBBtn = document.getElementById("multimodalCompareClearFaceBBtn");
const multimodalCompareVideoFileA = document.getElementById("multimodalCompareVideoFileA");
const multimodalCompareVideoFileB = document.getElementById("multimodalCompareVideoFileB");
const multimodalCompareStartHoursA = document.getElementById("multimodalCompareStartHoursA");
const multimodalCompareStartMinutesA = document.getElementById("multimodalCompareStartMinutesA");
const multimodalCompareStartSecondsA = document.getElementById("multimodalCompareStartSecondsA");
const multimodalCompareEndHoursA = document.getElementById("multimodalCompareEndHoursA");
const multimodalCompareEndMinutesA = document.getElementById("multimodalCompareEndMinutesA");
const multimodalCompareEndSecondsA = document.getElementById("multimodalCompareEndSecondsA");
const multimodalCompareStartHoursB = document.getElementById("multimodalCompareStartHoursB");
const multimodalCompareStartMinutesB = document.getElementById("multimodalCompareStartMinutesB");
const multimodalCompareStartSecondsB = document.getElementById("multimodalCompareStartSecondsB");
const multimodalCompareEndHoursB = document.getElementById("multimodalCompareEndHoursB");
const multimodalCompareEndMinutesB = document.getElementById("multimodalCompareEndMinutesB");
const multimodalCompareEndSecondsB = document.getElementById("multimodalCompareEndSecondsB");
const multimodalCompareSourceStatusA = document.getElementById("multimodalCompareSourceStatusA");
const multimodalCompareSourceStatusB = document.getElementById("multimodalCompareSourceStatusB");
const multimodalCompareFaceStatusA = document.getElementById("multimodalCompareFaceStatusA");
const multimodalCompareFaceStatusB = document.getElementById("multimodalCompareFaceStatusB");
const multimodalComparePreviewA = document.getElementById("multimodalComparePreviewA");
const multimodalComparePreviewB = document.getElementById("multimodalComparePreviewB");
const multimodalCompareFrameRate = document.getElementById("multimodalCompareFrameRate");
const multimodalComparePickOutputDirBtn = document.getElementById("multimodalComparePickOutputDirBtn");
const multimodalCompareOutputDirStatus = document.getElementById("multimodalCompareOutputDirStatus");
const runMultimodalCompareAbBtn = document.getElementById("runMultimodalCompareAbBtn");
const multimodalCompareAbRunStatus = document.getElementById("multimodalCompareAbRunStatus");
const multimodalCompareAbSummary = document.getElementById("multimodalCompareAbSummary");
const multimodalCompareAbAlignedView = document.getElementById("multimodalCompareAbAlignedView");
const multimodalCompareAbTimelineTable = document.getElementById("multimodalCompareAbTimelineTable");
const multimodalCompareAbIndicatorsTable = document.getElementById("multimodalCompareAbIndicatorsTable");
const multimodalCompareAbResultsCard = document.getElementById("multimodalCompareAbResultsCard");
const multimodalCompareAbToggleSettingsBtn = document.getElementById("multimodalCompareAbToggleSettingsBtn");
const multimodalCompareAbSettingsPanel = document.getElementById("multimodalCompareAbSettingsPanel");
const multimodalCompareAbSettingsContent = document.getElementById("multimodalCompareAbSettingsContent");
const runMultimodalYtdlpBtn = document.getElementById("runMultimodalYtdlpBtn");
const runMultimodalFramesBtn = document.getElementById("runMultimodalFramesBtn");
const runMultimodalAudioBtn = document.getElementById("runMultimodalAudioBtn");
const runMultimodalMotionBtn = document.getElementById("runMultimodalMotionBtn");
const runMultimodalAlignBtn = document.getElementById("runMultimodalAlignBtn");
const multimodalProgressDialog = document.getElementById("multimodalProgressDialog");
const multimodalProgressTitle = document.getElementById("multimodalProgressTitle");
const multimodalProgressMessage = document.getElementById("multimodalProgressMessage");
const multimodalProgressBar = document.getElementById("multimodalProgressBar");
const multimodalProgressValue = document.getElementById("multimodalProgressValue");
const suiviVariable = document.getElementById("suiviVariable");
const suiviFilterVariable = document.getElementById("suiviFilterVariable");
const suiviFilterModalite = document.getElementById("suiviFilterModalite");
const suiviInterviewsSelect = document.getElementById("suiviInterviewsSelect");
const suiviSelectAllBtn = document.getElementById("suiviSelectAllBtn");
const suiviClearAllBtn = document.getElementById("suiviClearAllBtn");
const suiviCorpusDisplay = document.getElementById("suiviCorpusDisplay");
const suiviModeNotice = document.getElementById("suiviModeNotice");
const suiviEmotionProfilesTabBtn = document.getElementById("suiviEmotionProfilesTabBtn");
const suiviEmotionProfilesTitle = document.getElementById("suiviEmotionProfilesTitle");
const suiviEmotionProfilesHelp = document.getElementById("suiviEmotionProfilesHelp");
const suiviValenceProfilesTitle = document.getElementById("suiviValenceProfilesTitle");
const suiviValenceProfilesHelp = document.getElementById("suiviValenceProfilesHelp");
const suiviSummaryCorpus = document.getElementById("suiviSummaryCorpus");
const suiviSummaryVariable = document.getElementById("suiviSummaryVariable");
const suiviSummaryFilter = document.getElementById("suiviSummaryFilter");
const suiviSummaryUnits = document.getElementById("suiviSummaryUnits");
const suiviSummaryOrder = document.getElementById("suiviSummaryOrder");
const suiviSummaryPreprocessing = document.getElementById("suiviSummaryPreprocessing");
const suiviSummaryMorpho = document.getElementById("suiviSummaryMorpho");

const topNavLinks = Array.from(document.querySelectorAll("[data-tab-target]"));
const panels = Array.from(document.querySelectorAll("[data-panel]"));
const chdSubNavLinks = Array.from(document.querySelectorAll("[data-subtab-target]"));
const chdSubPanels = Array.from(document.querySelectorAll("[data-subpanel]"));
const ldaSubNavLinks = Array.from(document.querySelectorAll("[data-lda-subtab-target]"));
const ldaSubPanels = Array.from(document.querySelectorAll("[data-lda-subpanel]"));
const suiviSubNavLinks = Array.from(document.querySelectorAll("[data-suivi-subtab-target]"));
const suiviSubPanels = Array.from(document.querySelectorAll("[data-suivi-subpanel]"));
const multimodalSubNavLinks = Array.from(document.querySelectorAll("[data-multimodal-subtab-target]"));
const multimodalSubPanels = Array.from(document.querySelectorAll("[data-multimodal-subpanel]"));
const motionResultTabLinks = Array.from(document.querySelectorAll("[data-motion-result-target]"));
const motionResultPanels = Array.from(document.querySelectorAll("[data-motion-result-panel]"));
const helpSubNavLinks = Array.from(document.querySelectorAll("[data-help-subtab-target]"));
const helpSubPanels = Array.from(document.querySelectorAll("[data-help-subpanel]"));
const chdConfigSourceCards = Array.from(document.querySelectorAll("[data-chd-config-source]"));
const simiConfigSourceCards = Array.from(document.querySelectorAll("[data-simi-config-source]"));
const ldaConfigSourceCards = Array.from(document.querySelectorAll("[data-lda-config-source]"));
const suiviConfigSourceCards = Array.from(document.querySelectorAll("[data-suivi-config-source]"));

const resultContainers = {
  chdDendrogramme: document.getElementById("chdDendrogramme"),
  chdStatsTable: document.getElementById("chdStatsTable"),
  chdConcordancier: document.getElementById("chdConcordancier"),
  chdWordclouds: document.getElementById("chdWordclouds"),
  afcClassesPlot: document.getElementById("afcClassesPlot"),
  afcTermsPlot: document.getElementById("afcTermsPlot"),
  afcTermsTable: document.getElementById("afcTermsTable"),
  afcVarsPlot: document.getElementById("afcVarsPlot"),
  afcVarsTable: document.getElementById("afcVarsTable"),
  afcEigTable: document.getElementById("afcEigTable"),
  suiviMeta: document.getElementById("suiviMeta"),
  suiviIndicatorsTable: document.getElementById("suiviIndicatorsTable"),
  suiviEntropyPlot: document.getElementById("suiviEntropyPlot"),
  suiviRedundancyPlot: document.getElementById("suiviRedundancyPlot"),
  suiviEmotionProfilesPlot: document.getElementById("suiviEmotionProfilesPlot"),
  suiviEmotionProfilesTable: document.getElementById("suiviEmotionProfilesTable"),
  suiviValenceProfilesPlot: document.getElementById("suiviValenceProfilesPlot"),
  suiviValenceProfilesTable: document.getElementById("suiviValenceProfilesTable"),
  suiviJsdSuccessivePlot: document.getElementById("suiviJsdSuccessivePlot"),
  suiviJsdSuccessiveTable: document.getElementById("suiviJsdSuccessiveTable"),
  suiviJsdReferencePlot: document.getElementById("suiviJsdReferencePlot"),
  suiviJsdReferenceTable: document.getElementById("suiviJsdReferenceTable"),
  suiviRupturesPlot: document.getElementById("suiviRupturesPlot"),
  suiviRupturesTable: document.getElementById("suiviRupturesTable"),
  suiviTermsTable: document.getElementById("suiviTermsTable"),
  suiviContributionsTable: document.getElementById("suiviContributionsTable"),
  suiviFrisesEmergences: document.getElementById("suiviFrisesEmergences"),
  suiviDivergentBars: document.getElementById("suiviDivergentBars"),
  suiviWaterfalls: document.getElementById("suiviWaterfalls"),
  suiviMatrixPlot: document.getElementById("suiviMatrixPlot"),
  suiviMatrixTable: document.getElementById("suiviMatrixTable"),
  suiviWordclouds: document.getElementById("suiviWordclouds"),
  ldaBubblePlot: document.getElementById("ldaBubblePlot"),
  ldaHeatmap: document.getElementById("ldaHeatmap"),
  ldaNetwork: document.getElementById("ldaNetwork"),
  ldaWordclouds: document.getElementById("ldaWordclouds"),
  ldaTopTerms: document.getElementById("ldaTopTerms"),
  ldaSegments: document.getElementById("ldaSegments"),
  ldaDocTopics: document.getElementById("ldaDocTopics"),
  ldaTopicWords: document.getElementById("ldaTopicWords"),
  simiGraph: document.getElementById("simiGraph")
};

const appState = {
  corpusFileName: null,
  exportsFolderName: null,
  outputDir: null,
  exportEntries: [],
  analysisHistory: [],
  activeAnalysisHistoryId: null,
  corpusText: "",
  afcStarredVariablesChoices: [],
  corpusStarredDocs: [],
  corpusStarredModalitiesByVariable: {},
  simiTermsChoices: [],
  simiTermsOrdered: [],
  simiTermsLoading: false,
  simiTermsError: null,
  objectUrls: [],
  bootstrapPromise: null,
  bootstrapReady: false,
  chdDendrogramFiles: new Map(),
  chdSegmentsByClass: new Map(),
  jsdConcordancierRows: [],
  suiviPresentation: {
    layer: "lexicale_brute",
    emotionLexicon: "",
    hasEmotionProfiles: false,
    hasValenceProfiles: false
  },
  multimodalLocalPaths: {
    cookies: "",
    audio: "",
    video: "",
    segments: "",
    imagesDir: ""
  },
  multimodalSelectedImageFiles: [],
  multimodalSelectedFaceSelection: null,
  multimodalImagePaths: [],
  multimodalSegmentsPreviewParsed: null,
  multimodalGeneratedPaths: {
    audio: "",
    video: "",
    segments: "",
    segmentsAligned: "",
    framesIndex: "",
    alignmentCsv: "",
    framesDir: "",
  },
  multimodalResults: {
    audio: null,
    mouvements: null,
    alignement: null,
    noeuds: null,
    segments: null
  },
  multimodalOutputDir: "",
  multimodalRunningScripts: {
    audio: false,
    mouvements: false,
    alignement: false,
    noeuds: false,
    extraction: false
  },
  multimodalPendingInputs: {
    cookies: false,
    audio: false,
    video: false,
    segments: false,
    images: false
  },
  multimodalInputErrors: {
    cookies: "",
    audio: "",
    video: "",
    segments: "",
    images: ""
  },
  multimodalComparisonAB: {
    outputDir: "",
    sources: {
      a: {
        preparedVideoPath: "",
        error: "",
        selectedFaceSelection: null,
        latestExtraction: null,
      },
      b: {
        preparedVideoPath: "",
        error: "",
        selectedFaceSelection: null,
        latestExtraction: null,
      },
    },
    running: false,
    result: null,
    settingsOpen: false,
    fullscreen: false,
  },
  afcTermsZoom: 1,
  simiZoom: 1,
  imagePreviewItems: [],
  imagePreviewIndex: -1,
  expressionAnnotations: [],
  chdContextMenu: null,
  termSegmentsExport: null,
  termChartExport: null
};

const DEFAULT_TICKET_IDLE_RELEASE_MS = 900000;
let latestTicketSnapshot = normalizeTicketSnapshot({});
let analysisExecutionInProgress = false;
let idleReleaseTimerId = null;
let lastTicketInteractionAt = Date.now();
let ticketReleasedLocally = false;

const MORPHO_CATEGORIES = [
  "ADJ",
  "ADJ_DEM",
  "ADJ_IND",
  "ADJ_INT",
  "ADJ_NUM",
  "ADJ_POS",
  "ADJ_SUP",
  "ADV",
  "ADV_SUP",
  "ART_DEF",
  "ART_IND",
  "AUX",
  "CON",
  "NOM",
  "NOM_SUP",
  "ONO",
  "PRE",
  "PRO_DEM",
  "PRO_IND",
  "PRO_PER",
  "PRO_POS",
  "PRO_REL",
  "VER",
  "VER_SUP",
  "AUTRE_FORME"
];

const ANNOTATION_MORPHO_CATEGORIES = MORPHO_CATEGORIES.filter(
  (category) => category !== "AUTRE_FORME"
);

const progression = createProgressionController({
  dialog: runProgressDialog,
  titleElement: runProgressTitle,
  messageElement: runProgressMessage,
  progressBarElement: runProgressBar,
  progressValueElement: runProgressValue,
  mainProgressElement: progress,
  mainProgressLabelElement: progressLabel
});

const bootstrapProgression = createProgressionController({
  dialog: startupBootstrapDialog,
  titleElement: startupBootstrapTitle,
  messageElement: startupBootstrapMessage,
  progressBarElement: startupBootstrapBar,
  progressValueElement: startupBootstrapValue
});

const multimodalProgression = createProgressionController({
  dialog: multimodalProgressDialog,
  titleElement: multimodalProgressTitle,
  messageElement: multimodalProgressMessage,
  progressBarElement: multimodalProgressBar,
  progressValueElement: multimodalProgressValue
});

let multimodalFaceSelectionDraft = null;
let multimodalFaceSelectionSession = null;

function getTauriInvoke() {
  return window.__TAURI__?.core?.invoke ?? null;
}

function waitMs(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function setSidebarTicketStatus(message, state = "idle") {
  if (sidebarStatus) {
    sidebarStatus.textContent = message;
  }
  if (sidebarStatusDot) {
    sidebarStatusDot.classList.remove("is-idle", "is-active", "is-waiting", "is-error");
    sidebarStatusDot.classList.add(`is-${state}`);
  }
  if (sidebarStatusPill) {
    sidebarStatusPill.dataset.state = state;
  }
}

function setSidebarRuntimeStatus(message = "", state = "info") {
  if (!sidebarRuntimeStatus) return;
  sidebarRuntimeStatus.textContent = String(message || "");
  sidebarRuntimeStatus.classList.remove("is-error", "is-success");
  if (state === "error") {
    sidebarRuntimeStatus.classList.add("is-error");
  } else if (state === "success") {
    sidebarRuntimeStatus.classList.add("is-success");
  }
}

function normalizeTicketSnapshot(snapshot) {
  return {
    enabled: Boolean(snapshot?.enabled),
    statut: String(snapshot?.statut || "inconnu"),
    position: snapshot?.position ?? null,
    active: Number(snapshot?.active || 0),
    queued: Number(snapshot?.queued || 0),
    maxActive: Number(snapshot?.max_active || 0),
    waitRefreshMs: Number(snapshot?.wait_refresh_ms || 10000),
    heartbeatMs: Number(snapshot?.heartbeat_ms || 30000),
    idleReleaseMs: Number(snapshot?.idle_release_ms || DEFAULT_TICKET_IDLE_RELEASE_MS),
    message: String(snapshot?.message || "")
  };
}

function updateReleaseAccessButton(snapshot = latestTicketSnapshot) {
  if (!releaseAccessBtn) return;
  const canRelease = Boolean(snapshot?.enabled) && ["actif", "attente"].includes(String(snapshot?.statut || ""));
  releaseAccessBtn.disabled = !canRelease || analysisExecutionInProgress;
}

function resolveIdleReleaseMs(snapshot = latestTicketSnapshot) {
  return Math.max(60000, Number(snapshot?.idleReleaseMs || DEFAULT_TICKET_IDLE_RELEASE_MS));
}

function rememberUserInteraction() {
  lastTicketInteractionAt = Date.now();
  scheduleIdleTicketRelease();
}

function rememberTicketSnapshot(snapshot) {
  latestTicketSnapshot = normalizeTicketSnapshot(snapshot);
  if (["actif", "attente"].includes(latestTicketSnapshot.statut)) {
    ticketReleasedLocally = false;
  }
  updateReleaseAccessButton(latestTicketSnapshot);
  scheduleIdleTicketRelease();
  return latestTicketSnapshot;
}

async function autoReleaseTicketAfterInactivity() {
  if (analysisExecutionInProgress) {
    return;
  }

  const hasLiveTicket = latestTicketSnapshot.enabled && ["actif", "attente"].includes(latestTicketSnapshot.statut);
  if (!hasLiveTicket) {
    return;
  }

  const idleReleaseMs = resolveIdleReleaseMs();
  if (Date.now() - lastTicketInteractionAt < idleReleaseMs) {
    scheduleIdleTicketRelease();
    return;
  }

  const snapshot = await releaseAnalysisTicket({ silent: true });
  if (snapshot) {
    setSidebarRuntimeStatus("Acces libere automatiquement apres inactivite.", "success");
    await refreshTicketSidebarStatus();
  }
}

function scheduleIdleTicketRelease() {
  if (idleReleaseTimerId) {
    window.clearTimeout(idleReleaseTimerId);
    idleReleaseTimerId = null;
  }

  if (analysisExecutionInProgress) {
    return;
  }

  const hasLiveTicket = latestTicketSnapshot.enabled && ["actif", "attente"].includes(latestTicketSnapshot.statut);
  if (!hasLiveTicket) {
    return;
  }

  const idleReleaseMs = resolveIdleReleaseMs();
  const remainingMs = Math.max(1000, idleReleaseMs - (Date.now() - lastTicketInteractionAt));
  idleReleaseTimerId = window.setTimeout(() => {
    void autoReleaseTicketAfterInactivity();
  }, remainingMs);
}

function releaseTicketOnPageHide() {
  if (analysisExecutionInProgress) {
    return;
  }
  if (!latestTicketSnapshot.enabled || !["actif", "attente"].includes(latestTicketSnapshot.statut)) {
    return;
  }
  void fetch("/api/tickets/release", {
    method: "POST",
    credentials: "same-origin",
    keepalive: true
  }).catch(() => {});
}

async function callTicketApi(path, { method = "GET", body = null } = {}) {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }

  if (!response.ok) {
    const detail = payload?.detail || payload?.message || `Erreur HTTP ${response.status}`;
    throw new Error(String(detail));
  }
  return normalizeTicketSnapshot(payload);
}

async function refreshTicketSidebarStatus() {
  try {
    const snapshot = rememberTicketSnapshot(await callTicketApi("/api/tickets/status"));
    if (ticketReleasedLocally && snapshot.enabled && !["actif", "attente"].includes(snapshot.statut)) {
      if (snapshot.statut === "occupee") {
        setSidebarTicketStatus("Acces libere pour cette session. Application reprise par un autre utilisateur.", "idle");
        return snapshot;
      }
      setSidebarTicketStatus("Acces libere pour cette session.", "idle");
      return snapshot;
    }
    if (!snapshot.enabled) {
      setSidebarTicketStatus("Application disponible", "idle");
      return snapshot;
    }
    if (snapshot.statut === "actif") {
      setSidebarTicketStatus("Votre ticket est actif", "active");
      return snapshot;
    }
    if (snapshot.statut === "attente") {
      setSidebarTicketStatus(`File d'attente : position ${snapshot.position || "?"}`, "waiting");
      return snapshot;
    }
    if (snapshot.statut === "occupee") {
      setSidebarTicketStatus("Application occupee", "waiting");
      return snapshot;
    }
    if (snapshot.statut === "erreur" || snapshot.statut === "refuse") {
      setSidebarTicketStatus(
        snapshot.statut === "refuse" ? "File d'attente pleine" : "Acces serveur indisponible",
        "error"
      );
      return snapshot;
    }
    setSidebarTicketStatus("Application disponible", "idle");
    return snapshot;
  } catch (error) {
    setSidebarTicketStatus("Statut utilisateur indisponible", "error");
    return rememberTicketSnapshot({ enabled: false, message: error?.message || String(error) });
  }
}

async function claimPageTicketOnOpen() {
  try {
    const snapshot = await claimAnalysisTicket();
    if (!snapshot.enabled) {
      setSidebarTicketStatus("Application disponible", "idle");
      return snapshot;
    }
    if (snapshot.statut === "actif") {
      setSidebarTicketStatus("Session reservee sur cette application", "active");
      return snapshot;
    }
    if (snapshot.statut === "attente") {
      setSidebarTicketStatus(`File d'attente : position ${snapshot.position || "?"}`, "waiting");
      return snapshot;
    }
    if (snapshot.statut === "erreur" || snapshot.statut === "refuse") {
      setSidebarTicketStatus(
        snapshot.statut === "refuse" ? "File d'attente pleine" : "Acces serveur indisponible",
        "error"
      );
      return snapshot;
    }
    setSidebarTicketStatus("Acces serveur indisponible", "error");
    return snapshot;
  } catch (error) {
    setSidebarTicketStatus("Statut utilisateur indisponible", "error");
    return null;
  }
}

async function claimAnalysisTicket() {
  return rememberTicketSnapshot(await callTicketApi("/api/tickets/claim", { method: "POST" }));
}

async function heartbeatAnalysisTicket() {
  return rememberTicketSnapshot(await callTicketApi("/api/tickets/heartbeat", { method: "POST" }));
}

async function releaseAnalysisTicket({ silent = false } = {}) {
  try {
    const snapshot = rememberTicketSnapshot(await callTicketApi("/api/tickets/release", { method: "POST" }));
    ticketReleasedLocally = true;
    if (!silent) {
      await refreshTicketSidebarStatus();
    }
    return snapshot;
  } catch (error) {
    if (!silent) {
      setSidebarTicketStatus("Liberation du ticket impossible", "error");
    }
    return null;
  }
}

async function waitForAnalysisTicket(progressionController, logger) {
  let snapshot = await claimAnalysisTicket();
  if (!snapshot.enabled) {
    setSidebarTicketStatus("Application disponible", "idle");
    logger("[info] Controle d'acces Redis inactif pour cette application.");
    return snapshot;
  }
  if (snapshot.statut === "erreur") {
    throw new Error("Controle d'acces temporairement indisponible.");
  }

  let lastWaitingMessage = "";
  while (snapshot.statut === "attente") {
    const waitingMessage = `Application occupee. Position dans la file : ${snapshot.position || "?"}.`;
    setSidebarTicketStatus(waitingMessage, "waiting");
    progressionController.set(8, waitingMessage);
    if (waitingMessage !== lastWaitingMessage) {
      logger(`[info] ${waitingMessage}`);
      lastWaitingMessage = waitingMessage;
    }
    await waitMs(snapshot.waitRefreshMs);
    snapshot = await claimAnalysisTicket();
  }

  if (snapshot.statut === "refuse") {
    throw new Error("File d'attente pleine pour cette application.");
  }

  if (snapshot.statut !== "actif") {
    throw new Error("Impossible d'obtenir un ticket actif pour lancer l'analyse.");
  }

  setSidebarTicketStatus("Ticket actif : analyse en cours", "active");
  progressionController.set(10, "Acces serveur obtenu. Lancement de l'analyse...");
  logger("[info] Ticket utilisateur actif. Lancement du job IRaMuTeQ Lite.");
  return snapshot;
}

async function openExternalUrl(url) {
  const safeUrl = String(url || "").trim();
  if (!safeUrl) return;

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    window.open(safeUrl, "_blank", "noopener,noreferrer");
    return;
  }

  try {
    await tauriInvoke("open_external_url", { url: safeUrl });
  } catch (error) {
    log(`[error] Ouverture du lien externe impossible : ${error?.message || String(error)}`);
  }
}

async function revealInFileManager(path) {
  const safePath = String(path || "").trim();
  if (!safePath) return;

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) return;

  try {
    await tauriInvoke("reveal_in_file_manager", { path: safePath });
  } catch (error) {
    log(`[error] Impossible d'ouvrir l'emplacement de l'archive : ${error?.message || String(error)}`);
  }
}

function setDownloadResultsStatus(message, { isError = false } = {}) {
  if (!downloadResultsStatus) return;
  downloadResultsStatus.textContent = message;
  downloadResultsStatus.classList.toggle("is-error", isError);
}

function artifactDataToText(artifact) {
  if (!artifact) return "";
  if (artifact.encoding === "base64") {
    const bytes = decodeBase64ToBytes(artifact.data || "");
    return new TextDecoder("utf-8").decode(bytes);
  }
  return String(artifact.data || "");
}

function artifactDataToObjectUrl(artifact) {
  if (!artifact) return "";
  const bits = artifact.encoding === "base64" ? [decodeBase64ToBytes(artifact.data || "")] : [artifact.data || ""];
  const blob = new Blob(bits, { type: artifact.mimeType || "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  appState.objectUrls.push(url);
  return url;
}

function renderInlineMarkdown(text) {
  let html = String(text || "");
  html = html.replace(/`([^`]+)`/g, (_match, code) => `<code>${escapeHtml(code)}</code>`);
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, href) => {
    const safeHref = String(href || "").replace(/"/g, "&quot;");
    return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });
  return html;
}

async function renderMarkdownIntoContainer(container, markdownText, options = {}) {
  if (!container) return;

  const lines = String(markdownText || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let index = 0;

  const flushParagraph = (buffer) => {
    if (!buffer.length) return;
    blocks.push(`<p>${renderInlineMarkdown(buffer.join(" ").trim())}</p>`);
    buffer.length = 0;
  };

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      index += 1;
      continue;
    }

    const imageMatch = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (imageMatch) {
      const alt = imageMatch[1] || "";
      const imagePath = imageMatch[2] || "";
      let imageHtml = `<p>${escapeHtml(alt || imagePath)}</p>`;
      const tauriInvoke = getTauriInvoke();
      if (tauriInvoke) {
        try {
          const asset = await tauriInvoke("read_help_file", { relativePath: imagePath });
          const src = artifactDataToObjectUrl(asset);
          imageHtml = `<figure class="markdown-figure"><img src="${src}" alt="${escapeHtml(alt)}" /><figcaption>${escapeHtml(alt)}</figcaption></figure>`;
        } catch (error) {
          imageHtml = `<p class="markdown-image-error">Image introuvable : ${escapeHtml(imagePath)}</p>`;
          log(`[error] Lecture image d'aide impossible (${imagePath}) : ${error?.message || String(error)}`);
        }
      }
      blocks.push(imageHtml);
      index += 1;
      continue;
    }

    if (/^>\s+/.test(trimmed)) {
      const quoteLines = [];
      while (index < lines.length && /^>\s+/.test(lines[index].trim())) {
        quoteLines.push(lines[index].trim().replace(/^>\s+/, ""));
        index += 1;
      }
      blocks.push(`<blockquote>${renderInlineMarkdown(quoteLines.join(" "))}</blockquote>`);
      continue;
    }

    if (/^-\s+/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^-\s+/.test(lines[index].trim())) {
        items.push(`<li>${renderInlineMarkdown(lines[index].trim().replace(/^-\s+/, ""))}</li>`);
        index += 1;
      }
      blocks.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(`<li>${renderInlineMarkdown(lines[index].trim().replace(/^\d+\.\s+/, ""))}</li>`);
        index += 1;
      }
      blocks.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    const paragraph = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,6})\s+/.test(lines[index].trim()) &&
      !/^-\s+/.test(lines[index].trim()) &&
      !/^\d+\.\s+/.test(lines[index].trim()) &&
      !/^>\s+/.test(lines[index].trim()) &&
      !/^!\[/.test(lines[index].trim())
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    flushParagraph(paragraph);
  }

  container.innerHTML = blocks.join("\n");
}

async function loadHelpMarkdown(container, relativePath) {
  if (!container) return;
  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    container.innerHTML = `<p>Le chargement de <code>${escapeHtml(relativePath)}</code> est disponible dans Tauri.</p>`;
    return;
  }

  try {
    const artifact = await tauriInvoke("read_help_file", { relativePath });
    const markdownText = artifactDataToText(artifact);
    await renderMarkdownIntoContainer(container, markdownText, { relativePath });
  } catch (error) {
    container.innerHTML = `<p>Impossible de lire <code>${escapeHtml(relativePath)}</code> : ${escapeHtml(error?.message || String(error))}</p>`;
    log(`[error] Lecture aide impossible (${relativePath}) : ${error?.message || String(error)}`);
  }
}

function updateDownloadResultsState() {
  const hasResults = Boolean(appState.outputDir) && Array.isArray(appState.exportEntries) && appState.exportEntries.length > 0;
  if (downloadResultsBtn) {
    downloadResultsBtn.disabled = !hasResults;
  }
  if (!hasResults) {
    setDownloadResultsStatus("Le téléchargement se fait depuis chaque analyse lancée.", { isError: false });
  }
}

function getAnalysisKindLabel(analysisKind) {
  if (analysisKind === "suivi") return "Trajectoire lexicale";
  if (analysisKind === "lda") return "LDA";
  if (analysisKind === "simi") return "Similitudes";
  if (analysisKind === "multimodal_audio") return "Multimodal · Audio";
  if (analysisKind === "multimodal_mouvements") return "Multimodal · Mouvements";
  if (analysisKind === "multimodal_alignement") return "Multimodal · Alignement";
  if (analysisKind === "multimodal_noeuds") return "Multimodal · Noeuds";
  return "CHD";
}

function formatAnalysisDateTime(value) {
  if (!value) return "";
  try {
    return new Intl.DateTimeFormat("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch (_error) {
    return "";
  }
}

function getAnalysisHistoryLabel(entry) {
  const kindLabel = getAnalysisKindLabel(entry?.analysisKind);
  const dateLabel = formatAnalysisDateTime(entry?.createdAt);
  return dateLabel ? `${kindLabel} · ${dateLabel}` : kindLabel;
}

function sanitizeFilenameSegment(value) {
  return String(value || "")
    .trim()
    .replace(/\.[^.]+$/, "")
    .replace(/[^\p{L}\p{N}_-]+/gu, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
}

function getAnalysisHistoryArchiveBaseName(entry) {
  const corpusPart = sanitizeFilenameSegment(entry?.corpusName) || "iramuteq";
  const kindPart = sanitizeFilenameSegment(getAnalysisKindLabel(entry?.analysisKind)) || "analyse";
  const createdAt = entry?.createdAt ? new Date(entry.createdAt) : new Date();
  const datePart = Number.isNaN(createdAt.getTime())
    ? "resultats"
    : [
        createdAt.getFullYear(),
        String(createdAt.getMonth() + 1).padStart(2, "0"),
        String(createdAt.getDate()).padStart(2, "0"),
        String(createdAt.getHours()).padStart(2, "0"),
        String(createdAt.getMinutes()).padStart(2, "0")
      ].join("");
  return `${corpusPart}_${kindPart}_${datePart}`;
}

async function activateAnalysisHistoryEntry(entryId) {
  const entry = appState.analysisHistory.find((item) => item.id === entryId);
  if (!entry || !Array.isArray(entry.artifacts) || !entry.artifacts.length) {
    log("[error] Réouverture de l'analyse impossible : aucun export mémorisé.");
    return;
  }

  appState.activeAnalysisHistoryId = entry.id;
  appState.outputDir = entry.outputDir || null;

  const virtualFiles = entry.artifacts.map((artifact) =>
    createVirtualFileFromArtifact(artifact, entry.folderName || entry.jobId || entry.id)
  );

  if (entry.navigationTarget === "multimodale") {
    log("[error] Cet historique provient de l'ancien module multimodal, retiré de cette version d'IRaMuTeQ Lite.");
    renderAnalysisHistory();
    return;
  }

  if (entry.navigationTarget === "suivi_longitudinal") {
    log("[error] Cet historique provient de l'ancien module de trajectoire longitudinale, retire de cette version d'IRaMuTeQ Lite.");
    renderAnalysisHistory();
    return;
  }

  await handleExportsFolderSelection(virtualFiles, entry.navigationTarget || "resultats_chd");
  renderAnalysisSteps(Array.isArray(entry.logs) ? entry.logs : []);
  renderAnalysisSummary(entry.summary || null);
  renderZipfChart(entry.summary || null);

  void refreshTicketSidebarStatus();
  log(`[info] Résultats rechargés : ${getAnalysisHistoryLabel(entry)}.`);
  renderAnalysisHistory();
}

function getMultimodalScriptNameForHistoryKind(analysisKind) {
  if (analysisKind === "multimodal_audio") return "audio.py";
  if (analysisKind === "multimodal_mouvements") return "mouvements.py";
  if (analysisKind === "multimodal_alignement") return "alignement.py";
  if (analysisKind === "multimodal_noeuds") return "noeuds.py";
  return "";
}

function getMultimodalSubtabForHistoryKind(analysisKind) {
  if (analysisKind === "multimodal_audio") return "multimodale_audio";
  if (analysisKind === "multimodal_mouvements") return "multimodale_mouvements";
  if (analysisKind === "multimodal_alignement") return "multimodale_alignement";
  if (analysisKind === "multimodal_noeuds") return "multimodale_noeuds";
  return "multimodale_sources";
}

function getMultimodalHistoryKind(scriptName) {
  if (scriptName === "audio.py") return "multimodal_audio";
  if (scriptName === "mouvements.py") return "multimodal_mouvements";
  if (scriptName === "alignement.py") return "multimodal_alignement";
  if (scriptName === "noeuds.py") return "multimodal_noeuds";
  return "multimodal_audio";
}

function renderAnalysisHistory() {
  if (!analysisHistory) return;

  analysisHistory.innerHTML = "";

  if (!Array.isArray(appState.analysisHistory) || !appState.analysisHistory.length) {
    const empty = document.createElement("p");
    empty.className = "muted analysis-history-empty";
    empty.textContent = "Les analyses lancées s'afficheront ici.";
    analysisHistory.appendChild(empty);
    return;
  }

  appState.analysisHistory.forEach((entry) => {
    const item = document.createElement("div");
    item.className = `analysis-history-item${entry.id === appState.activeAnalysisHistoryId ? " is-active" : ""}`;

    const mainButton = document.createElement("button");
    mainButton.type = "button";
    mainButton.className = "analysis-history-item-main";

    const title = document.createElement("span");
    title.className = "analysis-history-item-title";
    title.textContent = getAnalysisHistoryLabel(entry);

    const meta = document.createElement("span");
    meta.className = "analysis-history-item-meta";
    meta.textContent = entry.corpusName || "Corpus courant";

    mainButton.appendChild(title);
    mainButton.appendChild(meta);
    mainButton.addEventListener("click", () => {
      void activateAnalysisHistoryEntry(entry.id);
    });

    const downloadButton = document.createElement("button");
    downloadButton.type = "button";
    downloadButton.className = "secondary-button analysis-history-download";
    downloadButton.textContent = "Télécharger";
    downloadButton.addEventListener("click", () => {
      void downloadResultsArchive({
        outputDir: entry.outputDir,
        entryCount: Array.isArray(entry.artifacts) ? entry.artifacts.length : 0,
        archiveBaseName: getAnalysisHistoryArchiveBaseName(entry),
        pendingButton: downloadButton
      });
    });

    item.appendChild(mainButton);
    item.appendChild(downloadButton);
    analysisHistory.appendChild(item);
  });
}

function rememberAnalysisHistoryEntry(entry) {
  if (!entry || !Array.isArray(entry.artifacts) || !entry.artifacts.length) {
    return;
  }

  const normalizedEntry = {
    id: entry.id || entry.jobId || `${entry.analysisKind || "chd"}-${Date.now()}`,
    jobId: entry.jobId || null,
    analysisKind: entry.analysisKind || "chd",
    createdAt: entry.createdAt || new Date().toISOString(),
    corpusName: entry.corpusName || appState.corpusFileName || "",
    folderName: entry.folderName || entry.jobId || "exports",
    outputDir: entry.outputDir || null,
    navigationTarget: entry.navigationTarget || "resultats_chd",
    summary: entry.summary || null,
    logs: Array.isArray(entry.logs) ? entry.logs : [],
    artifacts: entry.artifacts
  };

  appState.analysisHistory = [
    normalizedEntry,
    ...appState.analysisHistory.filter((item) => item.id !== normalizedEntry.id)
  ];
  appState.activeAnalysisHistoryId = normalizedEntry.id;
  renderAnalysisHistory();
}

function splitCsvValues(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeStarredVariableName(value) {
  return String(value || "")
    .trim()
    .replace(/^\*/, "")
    .trim();
}

function getScopedSourceElement(scope, sourceId) {
  if (!scope) return null;
  return (
    scope.querySelector?.(`#${sourceId}`) ||
    scope.querySelector?.(`[data-source-id='${sourceId}']`) ||
    null
  );
}

function sortStarredModalities(values, order = "asc") {
  const uniqueValues = [...new Set((values || []).map((value) => String(value || "").trim()).filter(Boolean))];
  if (!uniqueValues.length) return [];

  const numericValues = uniqueValues.map((value) => Number(value));
  let sortedValues = [];
  if (numericValues.every((value) => Number.isFinite(value))) {
    sortedValues = [...uniqueValues].sort((left, right) => Number(left) - Number(right) || left.localeCompare(right));
  } else {
    const parsedDates = uniqueValues.map((value) => Date.parse(value));
    if (parsedDates.every((value) => Number.isFinite(value))) {
      sortedValues = [...uniqueValues].sort((left, right) => Date.parse(left) - Date.parse(right) || left.localeCompare(right));
    } else {
      sortedValues = [...uniqueValues].sort((left, right) =>
        left.localeCompare(right, undefined, { sensitivity: "base", numeric: true })
      );
    }
  }

  return order === "desc" ? sortedValues.reverse() : sortedValues;
}

function parseStarredToken(token) {
  const normalized = normalizeStarredVariableName(token);
  if (!normalized) return null;

  const separatorIndex = normalized.indexOf("_");
  if (separatorIndex === -1) {
    return {
      variable: normalized,
      value: "1"
    };
  }

  const variable = normalized.slice(0, separatorIndex).trim();
  const value = normalized.slice(separatorIndex + 1).trim() || "1";
  if (!variable) return null;
  return { variable, value };
}

function extractStarredMetadataFromCorpusText(text) {
  const variables = new Map();
  const modalitiesByVariable = new Map();
  const docs = [];
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const tokenPattern = /\*([A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9_-]*)/g;

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed.startsWith("****")) return;

    const docEntry = { index: docs.length + 1, variables: {} };
    const matches = [...trimmed.matchAll(tokenPattern)].map((match) => `*${match[1]}`);
    matches.forEach((token) => {
      const parsed = parseStarredToken(token);
      if (!parsed) return;
      const variableName = parsed.variable;
      const key = variableName.toLowerCase();
      if (!variables.has(key)) {
        variables.set(key, variableName);
      }
      if (!modalitiesByVariable.has(key)) {
        modalitiesByVariable.set(key, new Set());
      }
      modalitiesByVariable.get(key).add(parsed.value);
      if (!docEntry.variables[key]) {
        docEntry.variables[key] = parsed.value;
      }
    });
    docs.push(docEntry);
  });

  const sortedVariables = [...variables.values()].sort((left, right) =>
    left.localeCompare(right, undefined, { sensitivity: "base" })
  );
  const normalizedModalities = {};
  modalitiesByVariable.forEach((values, key) => {
    normalizedModalities[key] = sortStarredModalities([...values]);
  });

  return {
    variables: sortedVariables,
    modalitiesByVariable: normalizedModalities,
    docs
  };
}

function extractStarredVariablesFromCorpusText(text) {
  return extractStarredMetadataFromCorpusText(text).variables;
}

function renderAfcStarredVariablesPicker(card, options = {}) {
  if (!card) return;

  const { resetSelection = false } = options;
  const hiddenInput = card.querySelector("[data-afc-starred-selected-input]");
  const select = card.querySelector("[data-afc-starred-available-select]");
  const list = card.querySelector("[data-afc-starred-selected-list]");
  if (!hiddenInput || !select || !list) return;

  const available = [...appState.afcStarredVariablesChoices];
  const allowedMap = new Map(available.map((value) => [value.toLowerCase(), value]));
  const currentSelection = splitCsvValues(hiddenInput.value)
    .map((value) => normalizeStarredVariableName(value))
    .filter(Boolean);

  let selected = currentSelection
    .map((value) => allowedMap.get(value.toLowerCase()) || null)
    .filter(Boolean);

  if (resetSelection) {
    selected = [...available];
  } else if (!selected.length && available.length) {
    selected = [...available];
  }

  hiddenInput.value = [...new Set(selected)].join(", ");

  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choisir une variable";
  select.appendChild(placeholder);

  available
    .filter((value) => !selected.some((selectedValue) => selectedValue.toLowerCase() === value.toLowerCase()))
    .forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });

  list.innerHTML = "";
  list.hidden = false;
  if (!available.length) {
    list.appendChild(createEmptyState("Aucune variable étoilée détectée dans le corpus."));
    hiddenInput.value = "";
    return;
  }

  if (!selected.length) {
    list.hidden = true;
    return;
  }

  selected.forEach((value) => {
    const chip = document.createElement("div");
    chip.className = "chip-item";

    const label = document.createElement("span");
    label.className = "chip-item-label";
    label.textContent = value;

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "chip-item-remove";
    removeButton.setAttribute("aria-label", `Retirer ${value}`);
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => {
      hiddenInput.value = selected.filter((item) => item.toLowerCase() !== value.toLowerCase()).join(", ");
      renderAfcStarredVariablesPicker(card);
    });

    chip.appendChild(label);
    chip.appendChild(removeButton);
    list.appendChild(chip);
  });
}

function renderAfcStarredVariablesPickers(scope = document, options = {}) {
  scope
    .querySelectorAll("[data-afc-starred-variables-card]")
    .forEach((card) => renderAfcStarredVariablesPicker(card, options));
}

function getSelectedMultiSelectValues(select) {
  if (!(select instanceof HTMLSelectElement)) return [];
  return Array.from(select.selectedOptions).map((option) => option.value).filter(Boolean);
}

const SUIVI_TRAJECTOIRE_PRIORITY = ["seance", "date", "mois", "annee", "phase", "temps"];
const SUIVI_FILTRE_PRIORITY = ["journal", "source", "locuteur", "patient", "service"];

function sortSuiviVariables(values, priorities = []) {
  const priorityMap = new Map(
    priorities.map((value, index) => [String(value || "").trim().toLowerCase(), index])
  );

  return [...values].sort((left, right) => {
    const leftNormalized = normalizeStarredVariableName(left).toLowerCase();
    const rightNormalized = normalizeStarredVariableName(right).toLowerCase();
    const leftPriority = priorityMap.has(leftNormalized) ? priorityMap.get(leftNormalized) : Number.POSITIVE_INFINITY;
    const rightPriority = priorityMap.has(rightNormalized) ? priorityMap.get(rightNormalized) : Number.POSITIVE_INFINITY;

    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }

    return String(left).localeCompare(String(right), undefined, {
      sensitivity: "base",
      numeric: true
    });
  });
}

function resolveSuiviVariableName(scope = document) {
  const explicitValue = normalizeStarredVariableName(getScopedSourceElement(scope, "suiviVariable")?.value || "");
  const available = sortSuiviVariables(appState.afcStarredVariablesChoices, SUIVI_TRAJECTOIRE_PRIORITY)
    .map((value) => normalizeStarredVariableName(value))
    .filter(Boolean);

  if (!available.length) return "";

  const availableMap = new Map(available.map((value) => [value.toLowerCase(), value]));
  if (explicitValue) {
    return availableMap.get(explicitValue.toLowerCase()) || explicitValue;
  }

  const priorities = SUIVI_TRAJECTOIRE_PRIORITY;
  for (const candidate of priorities) {
    const matched = availableMap.get(candidate);
    if (matched) return matched;
  }

  return available[0] || "";
}

function getStoredModalitiesForVariable(variableName) {
  const normalizedName = normalizeStarredVariableName(variableName).toLowerCase();
  if (!normalizedName) return [];
  return appState.corpusStarredModalitiesByVariable[normalizedName] || [];
}

function getStoredModalitiesWithCountsForVariable(variableName) {
  const normalizedName = normalizeStarredVariableName(variableName).toLowerCase();
  if (!normalizedName) return [];

  if (!Array.isArray(appState.corpusStarredDocs) || !appState.corpusStarredDocs.length) {
    return getStoredModalitiesForVariable(variableName).map((value) => ({
      value,
      count: null
    }));
  }

  const counts = new Map();
  appState.corpusStarredDocs.forEach((doc) => {
    const value = String(doc.variables?.[normalizedName] || "").trim();
    if (!value) return;
    counts.set(value, (counts.get(value) || 0) + 1);
  });

  return sortStarredModalities([...counts.keys()]).map((value) => ({
    value,
    count: counts.get(value) || 0
  }));
}

function getSuiviAvailableUnits(scope = document) {
  const variableName = resolveSuiviVariableName(scope);
  if (!variableName) return [];

  const chronologyOrder = String(getScopedSourceElement(scope, "suiviChronologyOrder")?.value || "asc").trim() || "asc";
  const filterVariableName = normalizeStarredVariableName(getScopedSourceElement(scope, "suiviFilterVariable")?.value || "");
  const filterModality = String(getScopedSourceElement(scope, "suiviFilterModalite")?.value || "").trim();

  if (!Array.isArray(appState.corpusStarredDocs) || !appState.corpusStarredDocs.length) {
    return sortStarredModalities(getStoredModalitiesForVariable(variableName), chronologyOrder);
  }

  let docs = [...appState.corpusStarredDocs];
  if (filterVariableName && filterModality) {
    docs = docs.filter((doc) => String(doc.variables?.[filterVariableName.toLowerCase()] || "").trim() === filterModality);
  }

  const units = docs
    .map((doc) => String(doc.variables?.[variableName.toLowerCase()] || "").trim())
    .filter(Boolean);

  return sortStarredModalities(units, chronologyOrder);
}

function getSuiviEffectivePreprocessingLabel(scope = document) {
  const globalUseLemmas = Boolean(document.getElementById("useLemmas")?.checked);
  return globalUseLemmas ? "lemmes" : "formes";
}

function getSuiviAnalysisLayer(scope = document) {
  const value = String(getScopedSourceElement(scope, "suiviAnalysisLayer")?.value || "lexicale_brute").trim();
  return value === "emotionnelle" ? "emotionnelle" : "lexicale_brute";
}

function getSuiviEmotionLexicon(scope = document) {
  const value = String(getScopedSourceElement(scope, "suiviEmotionLexicon")?.value || "feel").trim().toLowerCase();
  return value === "nrc" ? "nrc" : "feel";
}

function getMeaningfulSuiviNote(note) {
  const text = String(note || "").trim();
  if (!text) return "";
  if (/^analyse longitudinale disponible\.?$/i.test(text)) return "";
  return text;
}

function applySuiviPresentation() {
  const layer = String(appState.suiviPresentation?.layer || "lexicale_brute").trim();
  const emotionLexicon = String(appState.suiviPresentation?.emotionLexicon || "").trim().toUpperCase();
  const isEmotion = layer === "emotionnelle";
  const hasEmotionProfiles = Boolean(appState.suiviPresentation?.hasEmotionProfiles);
  const hasValenceProfiles = Boolean(appState.suiviPresentation?.hasValenceProfiles);
  const note = getMeaningfulSuiviNote(appState.suiviPresentation?.note);

  if (suiviModeNotice) {
    suiviModeNotice.innerHTML = isEmotion
      ? `Couche active : <strong>trajectoire émotionnelle</strong>. La divergence compare ici des distributions d'émotions reconnues par ${escapeHtml(emotionLexicon || "FEEL/NRC")}.${note ? ` <strong>Note :</strong> ${escapeHtml(note)}` : ""}`
      : `Couche active : <strong>trajectoire lexicale brute</strong>. La divergence compare directement les distributions de mots ou de lemmes après prétraitement.`;
  }

  if (suiviEmotionProfilesTabBtn) {
    suiviEmotionProfilesTabBtn.textContent = isEmotion ? "Profils émotionnels" : "Profils émotionnels";
  }

  if (suiviEmotionProfilesTitle) {
    suiviEmotionProfilesTitle.textContent = isEmotion
      ? `Profils émotionnels${emotionLexicon ? ` · ${emotionLexicon}` : ""}`
      : "Profils émotionnels";
  }
  if (suiviEmotionProfilesHelp) {
    suiviEmotionProfilesHelp.textContent = isEmotion
      ? "Chaque entretien est résumé par une distribution d'émotions. Cette vue aide à voir quelles émotions dominent, se diversifient ou se resserrent dans le temps."
      : "Disponible uniquement pour la trajectoire émotionnelle. En mode lexical brut, la trajectoire reste centrée sur les mots, les contributions et les concordanciers.";
  }
  if (suiviValenceProfilesTitle) {
    suiviValenceProfilesTitle.textContent = "Résumé de valence positive / négative";
  }
  if (suiviValenceProfilesHelp) {
    suiviValenceProfilesHelp.textContent = isEmotion
      ? hasValenceProfiles
        ? "Ce résumé secondaire agrège les émotions en valence positive et négative lorsque le lexique émotionnel le permet."
        : "Le lexique émotionnel courant ne fournit pas ici de résumé de valence suffisamment exploitable."
      : "Disponible uniquement pour la trajectoire émotionnelle.";
  }
}

function extractSuiviPresentationFromMeta(parsed) {
  const mapping = new Map();
  rowsFromParsedCsv(parsed).forEach((row) => {
    const key = String(row.Indicateur || "").trim();
    const value = String(row.Valeur || "").trim();
    if (key) mapping.set(key, value);
  });

  const layerValue = (mapping.get("Couche d'analyse") || "").toLowerCase();
  const layer = layerValue.includes("emotion") ? "emotionnelle" : "lexicale_brute";

  appState.suiviPresentation = {
    layer,
    emotionLexicon: String(mapping.get("Lexique émotionnel") || "").trim(),
    hasEmotionProfiles: layer === "emotionnelle",
    hasValenceProfiles: false,
    note: String(mapping.get("Note") || "").trim()
  };
  applySuiviPresentation();
}

function buildSuiviMorphoSummaryText() {
  const morphoActive = Boolean(document.getElementById("morphoFilter")?.checked);
  if (!morphoActive) {
    return "Inactif.";
  }

  const categories = splitCsvValues(document.getElementById("posKeep")?.value || "");
  const excludeEtre = Boolean(document.getElementById("excludeEtre")?.checked);
  const keepUnknownForms = Boolean(document.getElementById("keepUnknownForms")?.checked);
  const parts = ["Actif"];
  parts.push(
    categories.length
      ? `catégories : ${categories.join(", ")}`
      : "aucune catégorie c_morpho sélectionnée"
  );
  parts.push(`« être » exclu : ${excludeEtre ? "oui" : "non"}`);
  parts.push(`formes hors lexique : ${keepUnknownForms ? "oui" : "non"}`);
  return parts.join(" · ");
}

function updateSuiviSummary(scope = document) {
  const resolvedVariable = resolveSuiviVariableName(scope);
  const filterVariableName = normalizeStarredVariableName(getScopedSourceElement(scope, "suiviFilterVariable")?.value || "");
  const filterModality = String(getScopedSourceElement(scope, "suiviFilterModalite")?.value || "").trim();
  const interviewsSelect = getScopedSourceElement(scope, "suiviInterviewsSelect");
  const selectedUnits = getSelectedMultiSelectValues(interviewsSelect);
  const availableUnits = getSuiviAvailableUnits(scope);
  const chronologyOrder = String(getScopedSourceElement(scope, "suiviChronologyOrder")?.value || "asc").trim() || "asc";
  const dictionarySource = String(document.getElementById("dictionarySource")?.value || "lexique_fr").trim() || "lexique_fr";
  const previewUnits = selectedUnits.slice(0, 4);

  if (suiviSummaryCorpus) {
    suiviSummaryCorpus.textContent = appState.corpusFileName || "Aucun corpus chargé.";
  }
  if (suiviCorpusDisplay) {
    suiviCorpusDisplay.textContent = appState.corpusFileName || "Aucun corpus chargé.";
  }
  if (suiviSummaryVariable) {
    suiviSummaryVariable.textContent = resolvedVariable ? `*${resolvedVariable}` : "Détection automatique.";
  }
  if (suiviSummaryFilter) {
    suiviSummaryFilter.textContent = filterVariableName && filterModality
      ? `*${filterVariableName} = ${filterModality}`
      : "Aucun filtre.";
  }
  if (suiviSummaryUnits) {
    if (!availableUnits.length) {
      suiviSummaryUnits.textContent = "Aucun entretien disponible.";
    } else {
      const suffix = previewUnits.length
        ? ` (${previewUnits.join(", ")}${selectedUnits.length > previewUnits.length ? ", ..." : ""})`
        : "";
      suiviSummaryUnits.textContent = `${selectedUnits.length} entretien(s) sélectionné(s) sur ${availableUnits.length}${suffix}`;
    }
  }
  if (suiviSummaryOrder) {
    suiviSummaryOrder.textContent = chronologyOrder === "desc" ? "Décroissant." : "Croissant.";
  }
  if (suiviSummaryPreprocessing) {
    suiviSummaryPreprocessing.textContent = `${dictionarySource} · ${getSuiviEffectivePreprocessingLabel(scope)}`;
  }
  if (suiviSummaryMorpho) {
    suiviSummaryMorpho.textContent = buildSuiviMorphoSummaryText();
  }
}

function renderSuiviControls(scope = document, options = {}) {
  const { resetSelection = false } = options;
  const variableSelect = getScopedSourceElement(scope, "suiviVariable");
  const filterVariableSelect = getScopedSourceElement(scope, "suiviFilterVariable");
  const filterModalitySelect = getScopedSourceElement(scope, "suiviFilterModalite");
  const interviewsSelect = getScopedSourceElement(scope, "suiviInterviewsSelect");
  const chronologyOrderSelect = getScopedSourceElement(scope, "suiviChronologyOrder");
  const corpusDisplay = getScopedSourceElement(scope, "suiviCorpusDisplay");
  const analysisLayerSelect = getScopedSourceElement(scope, "suiviAnalysisLayer");
  const emotionLexiconSelect = getScopedSourceElement(scope, "suiviEmotionLexicon");
  const lexicalUnitSelect = getScopedSourceElement(scope, "suiviLexicalUnit");
  const lexicalUnitHelp = getScopedSourceElement(scope, "suiviLexicalUnitHelp");

  if (!(variableSelect instanceof HTMLSelectElement)) return;
  const isEmotionLayer = getSuiviAnalysisLayer(scope) === "emotionnelle";

  if (emotionLexiconSelect instanceof HTMLSelectElement) {
    emotionLexiconSelect.disabled = !isEmotionLayer;
  }
  if (lexicalUnitSelect instanceof HTMLSelectElement) {
    lexicalUnitSelect.disabled = isEmotionLayer;
    if (isEmotionLayer) {
      lexicalUnitSelect.value = "unigramme";
    }
  }
  if (lexicalUnitHelp) {
    lexicalUnitHelp.textContent = isEmotionLayer
      ? "En trajectoire émotionnelle, le calcul repose sur les mots/lemmes simples. Les bigrammes sont donc désactivés."
      : "Les bigrammes sont utiles pour la trajectoire lexicale brute. La trajectoire émotionnelle repose sur les mots/lemmes simples.";
  }
  if (analysisLayerSelect instanceof HTMLSelectElement) {
    analysisLayerSelect.title = isEmotionLayer
      ? "Mode émotionnel : distribution d'émotions reconnues par un lexique FEEL ou NRC."
      : "Mode lexical brut : distribution directe des mots ou lemmes.";
  }
  if (scope === document && suiviModeNotice) {
    const emotionLexicon = getSuiviEmotionLexicon(scope).toUpperCase();
    suiviModeNotice.innerHTML = isEmotionLayer
      ? `Couche sélectionnée : <strong>trajectoire émotionnelle</strong>. La divergence portera sur des distributions d'émotions reconnues par ${escapeHtml(emotionLexicon)}.`
      : `Couche sélectionnée : <strong>trajectoire lexicale brute</strong>. La divergence portera directement sur les distributions de mots ou de lemmes.`;
  }

  const available = sortSuiviVariables(appState.afcStarredVariablesChoices, SUIVI_TRAJECTOIRE_PRIORITY);
  const current = normalizeStarredVariableName(variableSelect.value);
  const normalizedAvailable = new Map(available.map((value) => [value.toLowerCase(), value]));
  const preserved = current ? normalizedAvailable.get(current.toLowerCase()) || "" : "";

  variableSelect.innerHTML = "";

  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = "Détection auto (priorité : *seance, *date, *mois, *annee, *phase)";
  variableSelect.appendChild(autoOption);

  available.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    variableSelect.appendChild(option);
  });

  variableSelect.value = preserved;
  const resolvedVariable = resolveSuiviVariableName(scope);

  if (corpusDisplay) {
    if (!appState.corpusFileName) {
      corpusDisplay.textContent = "Aucun corpus chargé.";
    } else if (resolvedVariable) {
      corpusDisplay.textContent = `${appState.corpusFileName} · variable retenue : *${resolvedVariable}`;
    } else {
      corpusDisplay.textContent = appState.corpusFileName;
    }
  }

  if (filterVariableSelect instanceof HTMLSelectElement) {
    const currentFilterVariable = normalizeStarredVariableName(filterVariableSelect.value);
    const preservedFilterVariable = currentFilterVariable
      ? normalizedAvailable.get(currentFilterVariable.toLowerCase()) || ""
      : "";
    const availableFilterVariables = sortSuiviVariables(available, SUIVI_FILTRE_PRIORITY);

    filterVariableSelect.innerHTML = "";
    const emptyFilterOption = document.createElement("option");
    emptyFilterOption.value = "";
    emptyFilterOption.textContent = "Aucun filtre";
    filterVariableSelect.appendChild(emptyFilterOption);

    availableFilterVariables.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      filterVariableSelect.appendChild(option);
    });

    filterVariableSelect.value = preservedFilterVariable;
  }

  if (filterModalitySelect instanceof HTMLSelectElement) {
    const selectedFilterVariable = normalizeStarredVariableName(filterVariableSelect?.value || "");
    const availableModalities = getStoredModalitiesWithCountsForVariable(selectedFilterVariable);
    const currentFilterModality = String(filterModalitySelect.value || "").trim();
    const preservedFilterModality = availableModalities.some(({ value }) => value === currentFilterModality)
      ? currentFilterModality
      : "";

    filterModalitySelect.innerHTML = "";
    const allModalitiesOption = document.createElement("option");
    allModalitiesOption.value = "";
    allModalitiesOption.textContent = selectedFilterVariable
      ? `Toutes les modalités de *${selectedFilterVariable}`
      : "Tous les sous-corpus";
    filterModalitySelect.appendChild(allModalitiesOption);

    availableModalities.forEach(({ value, count }) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = Number.isFinite(count) ? `${value} (${count})` : value;
      filterModalitySelect.appendChild(option);
    });

    filterModalitySelect.value = preservedFilterModality;
    filterModalitySelect.disabled = !availableModalities.length;
  }

  if (interviewsSelect instanceof HTMLSelectElement) {
    const selectedBefore = getSelectedMultiSelectValues(interviewsSelect);
    const availableUnits = getSuiviAvailableUnits(scope);
    const preservedUnits = resetSelection
      ? [...availableUnits]
      : selectedBefore.filter((value) => availableUnits.includes(value));
    const finalSelection = preservedUnits.length ? preservedUnits : [...availableUnits];

    interviewsSelect.innerHTML = "";
    availableUnits.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      option.selected = finalSelection.includes(value);
      interviewsSelect.appendChild(option);
    });

    interviewsSelect.disabled = !availableUnits.length;
  }

  if (chronologyOrderSelect instanceof HTMLSelectElement) {
    chronologyOrderSelect.disabled = !(interviewsSelect instanceof HTMLSelectElement) || interviewsSelect.options.length === 0;
  }

  if (scope === document) {
    updateSuiviSummary(scope);
  }
}

function renderSuiviVariableSelect(scope = document, options = {}) {
  renderSuiviControls(scope, options);
}

function resetSimiTermsState() {
  appState.simiTermsChoices = [];
  appState.simiTermsOrdered = [];
  appState.simiTermsLoading = false;
  appState.simiTermsError = null;
}

function syncSimiTermsChoicesFromChdStats(parsed) {
  resetSimiTermsState();

  if (!parsed || !Array.isArray(parsed.headers) || !Array.isArray(parsed.rows) || !parsed.rows.length) {
    return;
  }

  const termIndex = headerIndex(parsed.headers, ["terme", "forme"]);
  const frequencyIndex = headerIndex(parsed.headers, ["frequency", "occ_total", "occ_st", "eff_total"]);
  if (termIndex === -1 || frequencyIndex === -1) {
    return;
  }

  const termsMap = new Map();
  parsed.rows.forEach((row) => {
    const term = String(row[termIndex] || "").trim();
    if (!term) return;
    const frequency = Number.parseFloat(String(row[frequencyIndex] || "").replace(",", "."));
    const safeFrequency = Number.isFinite(frequency) ? frequency : 0;
    const existing = termsMap.get(term);
    if (!existing || safeFrequency > existing.frequency) {
      termsMap.set(term, {
        term,
        frequency: safeFrequency,
        label: `${term} (${Math.round(safeFrequency)})`
      });
    }
  });

  const choices = [...termsMap.values()].sort((left, right) => {
    if (right.frequency !== left.frequency) return right.frequency - left.frequency;
    return left.term.localeCompare(right.term, undefined, { sensitivity: "base" });
  });

  appState.simiTermsChoices = choices;
  appState.simiTermsOrdered = choices.map((choice) => choice.term);
}

function renderSimiTermsPicker(context, options = {}) {
  if (!context) return;
  const { resetSelection = false } = options;

  const hiddenInput = context.querySelector("[data-simi-terms-input]");
  const topTermsInput = context.querySelector("[data-simi-top-terms-input]");
  const meta = context.querySelector("[data-simi-terms-meta]");
  const list = context.querySelector("[data-simi-terms-list]");
  if (!hiddenInput || !topTermsInput || !meta || !list) return;

  list.innerHTML = "";

  const limit = Math.max(1, Number(topTermsInput.value) || 100);
  const choices = appState.simiTermsChoices.slice(0, limit);
  if (!choices.length) {
    meta.textContent = "Realisez d'abord une CHD pour alimenter les termes de similitudes.";
    list.appendChild(
      createEmptyState("Aucune CHD disponible. Lancez une CHD, puis revenez ici pour utiliser ses termes les plus fréquents.")
    );
    hiddenInput.value = "";
    return;
  }

  const currentSelection = splitCsvValues(hiddenInput.value);
  const allowedTerms = new Set(choices.map((choice) => choice.term));
  const selectedTerms = (resetSelection || !currentSelection.length
    ? choices.map((choice) => choice.term)
    : currentSelection).filter((term) => allowedTerms.has(term));

  hiddenInput.value = selectedTerms.join(", ");
  meta.textContent = `${selectedTerms.length} mot(s) retenu(s) sur ${choices.length} proposé(s) à partir des termes les plus fréquents de la CHD.`;

  if (!selectedTerms.length) {
    list.appendChild(createEmptyState("Aucun mot retenu. Le top des termes sera alors réappliqué par défaut."));
    return;
  }

  const choicesByTerm = new Map(choices.map((choice) => [choice.term, choice]));
  selectedTerms.forEach((term) => {
    const choice = choicesByTerm.get(term);
    if (!choice) return;

    const chip = document.createElement("div");
    chip.className = "selected-term-chip";

    const label = document.createElement("span");
    label.className = "selected-term-chip-label";
    label.textContent = choice.label;

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "selected-term-chip-remove";
    removeButton.setAttribute("aria-label", `Exclure ${choice.term}`);
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => {
      hiddenInput.value = selectedTerms.filter((item) => item !== term).join(", ");
      renderSimiTermsPicker(context);
    });

    chip.appendChild(label);
    chip.appendChild(removeButton);
    list.appendChild(chip);
  });
}

function renderSimiTermsPickers(scope = document, options = {}) {
  scope.querySelectorAll("[data-simi-config-card]").forEach((card) => renderSimiTermsPicker(card, options));
}

function renderMorphoPicker(card) {
  if (!card) return;
  const hiddenInput = card.querySelector("[data-morpho-selected-input]");
  const select = card.querySelector("[data-morpho-available-select]");
  const list = card.querySelector("[data-morpho-selected-list]");
  if (!hiddenInput || !select || !list) return;

  const selected = splitCsvValues(hiddenInput.value).map((value) => value.toUpperCase());
  const uniqueSelected = [...new Set(selected)].filter((value) => MORPHO_CATEGORIES.includes(value));
  hiddenInput.value = uniqueSelected.join(", ");

  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choisir une catégorie";
  select.appendChild(placeholder);

  MORPHO_CATEGORIES.filter((category) => !uniqueSelected.includes(category)).forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    select.appendChild(option);
  });

  list.innerHTML = "";
  if (!uniqueSelected.length) {
    list.appendChild(createEmptyState("Aucune catégorie sélectionnée."));
    return;
  }

  uniqueSelected.forEach((category) => {
    const chip = document.createElement("div");
    chip.className = "chip-item";

    const label = document.createElement("span");
    label.className = "chip-item-label";
    label.textContent = category;

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "chip-item-remove";
    removeButton.setAttribute("aria-label", `Retirer ${category}`);
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => {
      hiddenInput.value = uniqueSelected.filter((item) => item !== category).join(", ");
      renderMorphoPicker(card);
    });

    chip.appendChild(label);
    chip.appendChild(removeButton);
    list.appendChild(chip);
  });
}

function renderMorphoPickers(scope = document) {
  scope.querySelectorAll("[data-chd-morpho-card]").forEach((card) => renderMorphoPicker(card));
}

function renderLdaMorphoPicker(card) {
  if (!card) return;
  const hiddenInput = card.querySelector("[data-lda-morpho-selected-input]");
  const select = card.querySelector("[data-lda-morpho-available-select]");
  const list = card.querySelector("[data-lda-morpho-selected-list]");
  if (!hiddenInput || !select || !list) return;

  const selected = splitCsvValues(hiddenInput.value).map((value) => value.toUpperCase());
  const uniqueSelected = [...new Set(selected)].filter((value) => MORPHO_CATEGORIES.includes(value));
  hiddenInput.value = uniqueSelected.join(", ");

  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choisir une catégorie";
  select.appendChild(placeholder);

  MORPHO_CATEGORIES.filter((category) => !uniqueSelected.includes(category)).forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    select.appendChild(option);
  });

  list.innerHTML = "";
  if (!uniqueSelected.length) {
    list.appendChild(createEmptyState("Aucune catégorie sélectionnée."));
    return;
  }

  uniqueSelected.forEach((category) => {
    const chip = document.createElement("div");
    chip.className = "chip-item";

    const label = document.createElement("span");
    label.className = "chip-item-label";
    label.textContent = category;

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "chip-item-remove";
    removeButton.setAttribute("aria-label", `Retirer ${category}`);
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => {
      hiddenInput.value = uniqueSelected.filter((item) => item !== category).join(", ");
      renderLdaMorphoPicker(card);
    });

    chip.appendChild(label);
    chip.appendChild(removeButton);
    list.appendChild(chip);
  });
}

function renderLdaMorphoPickers(scope = document) {
  scope.querySelectorAll("[data-lda-morpho-card]").forEach((card) => renderLdaMorphoPicker(card));
}

function renderClassificationModeCard(card) {
  if (!card) return;
  const hiddenInput = card.querySelector("#classificationMode, [data-source-id='classificationMode']");
  const radios = Array.from(card.querySelectorAll("[data-classification-radio]"));
  const rstFields = card.querySelector("[data-rst-fields]");
  if (!hiddenInput || !radios.length || !rstFields) return;

  const currentValue = hiddenInput.value === "double" ? "double" : "simple";
  hiddenInput.value = currentValue;
  radios.forEach((radio) => {
    radio.checked = radio.value === currentValue;
  });
  rstFields.hidden = currentValue !== "double";
  rstFields.style.display = currentValue === "double" ? "grid" : "none";
}

function renderClassificationModeCards(scope = document) {
  scope.querySelectorAll("[data-classification-mode-card]").forEach((card) => renderClassificationModeCard(card));
}

function buildAnalysesConfig(analysisKind = "chd") {
  switch (analysisKind) {
    case "suivi":
      return {
        chd: false,
        afc: false,
        simi: false,
        lda: false,
        suivi: true
      };
    case "lda":
      return {
        chd: false,
        afc: false,
        simi: false,
        lda: true,
        suivi: false
      };
    case "simi":
      return {
        chd: false,
        afc: false,
        simi: true,
        lda: false,
        suivi: false
      };
    case "chd":
    default:
      return {
        chd: true,
        afc: true,
        simi: false,
        lda: false,
        suivi: false
      };
  }
}

function computeDendrogramSizing() {
  const paneWidth = Math.round(resultContainers.chdDendrogramme?.getBoundingClientRect().width || 0);
  const viewportWidth = Math.round(window.innerWidth || 0);
  const baseWidth = paneWidth > 0 ? paneWidth : Math.max(960, viewportWidth - 180);
  const displayWidth = Math.max(880, Math.min(1600, baseWidth));
  const pixelRatio = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  const exportWidth = Math.max(1200, Math.min(2400, Math.round(displayWidth * pixelRatio)));
  const exportHeight = Math.max(620, Math.round(exportWidth * 0.52));

  return {
    displayWidth,
    exportWidth,
    exportHeight
  };
}

function syncDendrogramSizing() {
  const { displayWidth } = computeDendrogramSizing();
  resultContainers.chdDendrogramme?.style.setProperty("--dendrogram-display-width", `${displayWidth}px`);
}

function buildJobConfig(analysisKind = "chd") {
  const simiThresholdValue = Number(document.getElementById("simiThreshold").value);
  const dendrogramSizing = computeDendrogramSizing();
  const globalUseLemmas = document.getElementById("useLemmas").checked;
  const effectiveUseLemmas = globalUseLemmas;
  const expressionAnnotations = appState.expressionAnnotations.map((entry) => ({
    dic_mot: normalizeAnnotationSelectionValue(entry.dic_mot),
    dic_norm: normalizeAnnotationSelectionValue(entry.dic_norm),
    dic_morpho: String(entry.dic_morpho || "").trim()
  }));

  return {
    analyses: buildAnalysesConfig(analysisKind),
    segment_size: Number(document.getElementById("segmentSize").value) || 40,
    segmenter_sur_ponctuation_forte: document.getElementById("useStrongPunctuation").checked,
    min_docfreq: Number(document.getElementById("minFreq").value) || 1,
    max_p: Number(document.getElementById("maxP").value) || 0.05,
    filtrer_affichage_pvalue: document.getElementById("filterPvalue").checked,
    k_iramuteq: Number(document.getElementById("kIramuteq").value) || 3,
    iramuteq_max_formes: Number(document.getElementById("iramuteqMaxFormes").value) || 20000,
    iramuteq_mincl_mode: document.getElementById("minclMode").value,
    iramuteq_mincl: Number(document.getElementById("minclManual").value) || 1,
    iramuteq_classif_mode: document.getElementById("classificationMode").value,
    iramuteq_rst1: Number(document.getElementById("rst1").value) || 12,
    iramuteq_rst2: Number(document.getElementById("rst2").value) || 14,
    iramuteq_svd_method: document.getElementById("svdMethod").value,
    iramuteq_stats_mode: document.getElementById("statsMode").value,
    source_dictionnaire: document.getElementById("dictionarySource").value,
    lexique_utiliser_lemmes: effectiveUseLemmas,
    expression_utiliser_dictionnaire: document.getElementById("useExpressions").checked,
    utiliser_add_expression: document.getElementById("useAnnotationExpressions").checked,
    expression_annotations: expressionAnnotations,
    nettoyage_caracteres: document.getElementById("cleanChars").checked,
    supprimer_ponctuation: document.getElementById("removePunctuation").checked,
    supprimer_chiffres: document.getElementById("removeDigits").checked,
    supprimer_apostrophes: document.getElementById("removeApostrophes").checked,
    remplacer_tirets_espaces: document.getElementById("replaceHyphen").checked,
    retirer_stopwords: document.getElementById("removeStopwords").checked,
    filtrage_morpho: document.getElementById("morphoFilter").checked,
    pos_lexique_a_conserver: splitCsvValues(document.getElementById("posKeep").value),
    morpho_exclure_etre_verbe: document.getElementById("excludeEtre").checked,
    morpho_conserver_hors_lexique: document.getElementById("keepUnknownForms").checked,
    afc_reduire_chevauchement: document.getElementById("reduceOverlap").checked,
    afc_taille_mots: document.getElementById("wordSizeMode").value,
    afc_variables_etoilees: splitCsvValues(document.getElementById("afcStarredVariables").value),
    suivi_variable_etoilee: normalizeStarredVariableName(document.getElementById("suiviVariable")?.value || ""),
    suivi_filtre_variable_etoilee: normalizeStarredVariableName(document.getElementById("suiviFilterVariable")?.value || ""),
    suivi_filtre_modalite: String(document.getElementById("suiviFilterModalite")?.value || "").trim(),
    suivi_modalites_selectionnees: getSelectedMultiSelectValues(document.getElementById("suiviInterviewsSelect")),
    suivi_ordre_chronologique: String(document.getElementById("suiviChronologyOrder")?.value || "asc").trim() || "asc",
    suivi_couche_analyse: String(document.getElementById("suiviAnalysisLayer")?.value || "lexicale_brute").trim() || "lexicale_brute",
    suivi_lexique_emotionnel: String(document.getElementById("suiviEmotionLexicon")?.value || "feel").trim() || "feel",
    suivi_unite_lexicale: String(document.getElementById("suiviLexicalUnit")?.value || "unigramme").trim() || "unigramme",
    suivi_top_terms: Math.max(3, Number(document.getElementById("suiviTopTerms")?.value) || 20),
    suivi_amplification_signal: Math.max(1, Number(document.getElementById("suiviSignalAmplification")?.value) || 1),
    top_n: Number(document.getElementById("topNWords").value) || 20,
    simi_method: document.getElementById("simiMethod").value,
    simi_seuil: Number.isFinite(simiThresholdValue) && simiThresholdValue > 0 ? simiThresholdValue : null,
    simi_top_terms: Number(document.getElementById("simiTopTerms").value) || 100,
    simi_terms_selected: splitCsvValues(document.getElementById("simiTermsSelected").value),
    simi_max_tree: document.getElementById("simiMaxTree").checked,
    simi_layout: document.getElementById("simiLayout").value,
    simi_edge_labels: document.getElementById("simiEdgeLabels").checked,
    simi_edge_width_by_index: document.getElementById("simiEdgeWidth").checked,
    simi_vertex_text_by_freq: document.getElementById("simiVertexText").checked,
    simi_communities: document.getElementById("simiCommunities").checked,
    simi_community_method: document.getElementById("simiCommunityMethod").value,
    simi_halo: document.getElementById("simiHalo").checked,
    chd_dendrogram_width_px: dendrogramSizing.exportWidth,
    chd_dendrogram_height_px: dendrogramSizing.exportHeight,
    lda_mode_unite: document.getElementById("language").value,
    lda_k: Math.max(2, Number(document.getElementById("ldaK").value) || 6),
    lda_n_terms: Math.max(3, Number(document.getElementById("ldaTerms").value) || 8),
    lda_min_df: Math.max(1, Number(document.getElementById("ldaMinDf").value) || 1),
    lda_max_df: Math.min(1, Math.max(0.01, Number(document.getElementById("ldaMaxDf").value) || 0.95)),
    lda_max_iter: Math.max(1, Number(document.getElementById("ldaMaxIter").value) || 100),
    lda_ngram_range: splitCsvValues(document.getElementById("ldaNgramRange").value),
    lda_segment_size: Number(document.getElementById("ldaSegmentSize").value) || 40,
    lda_segmenter_sur_ponctuation_forte: document.getElementById("ldaStrongPunctuation").checked,
    lda_retirer_stopwords: document.getElementById("ldaStopwords").checked,
    lda_filtrage_morpho: document.getElementById("ldaMorpho").checked,
    lda_pos_keep: splitCsvValues(document.getElementById("ldaPosKeep").value)
  };
}

function decodeBase64ToBytes(base64Value) {
  const binary = window.atob(base64Value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function createVirtualFileFromArtifact(artifact, folderName) {
  const bits = artifact.encoding === "base64" ? [decodeBase64ToBytes(artifact.data)] : [artifact.data];
  const filename = artifact.relativePath.split("/").pop() || artifact.relativePath;
  const file = new File(bits, filename, {
    type: artifact.mimeType || "application/octet-stream"
  });
  Object.defineProperty(file, "virtualRelativePath", {
    value: `${folderName}/${artifact.relativePath}`,
    configurable: true
  });
  return file;
}

async function ensureDependenciesReady() {
  if (appState.bootstrapPromise) {
    return appState.bootstrapPromise;
  }

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    appState.bootstrapReady = true;
    return Promise.resolve({ success: true, message: "Bootstrap ignore hors Tauri." });
  }

  appState.bootstrapPromise = (async () => {
    bootstrapProgression.open(
      "Vérification de l'environnement",
      "Vérification des dépendances R et Python nécessaires au lancement."
    );
    bootstrapProgression.set(8, "Analyse des dépendances...");
    setSidebarRuntimeStatus("Verification des dependances");
    log("[info] Vérification des dépendances R et Python nécessaires au lancement.");

    try {
      bootstrapProgression.set(42, "Controle des dependances de l'image et installation si necessaire...");
      const payload = await tauriInvoke("bootstrap_dependencies");
      if (payload.success) {
        appState.bootstrapReady = true;
        if (Array.isArray(payload.installedNow) && payload.installedNow.length) {
          log(`[info] Dépendances installées : ${payload.installedNow.join(", ")}`);
        } else {
          log("[info] Dépendances R/Python déjà disponibles.");
        }
        if (payload.library) {
          log(`[info] Librairie R utilisateur: ${payload.library}`);
        }
        if (payload.rscript) {
          log(`[info] Rscript détecté : ${payload.rscript}`);
        }
        if (payload.python) {
          log(`[info] Python détecté : ${payload.python}`);
        }
        void refreshTicketSidebarStatus();
        bootstrapProgression.set(100, "Environnement prêt.");
      } else {
        appState.bootstrapReady = false;
        appState.bootstrapPromise = null;
        setSidebarRuntimeStatus("Packages incomplets (voir logs)", "error");
        const blockingMessage = payload.blockingMessage || payload.message || "Bootstrap des packages en échec.";
        const optionalMessage = payload.optionalMessage || "";
        const detailsMessage = payload.detailsMessage || "";

        log(`[error] ${blockingMessage}`);
        if (detailsMessage) {
          log(`[info] Détail bootstrap : ${detailsMessage}`);
        }
        if (!blockingMessage && Array.isArray(payload.missingAfter) && payload.missingAfter.length) {
          log(`[error] Dépendances encore manquantes : ${payload.missingAfter.join(", ")}`);
        }
        if (optionalMessage) {
          log(`[info] ${optionalMessage}`);
        }
        if (payload.rscript) {
          log(`[info] Rscript utilisé : ${payload.rscript}`);
        }
        if (payload.python) {
          log(`[info] Python utilisé : ${payload.python}`);
        }
        bootstrapProgression.set(100, "Certaines dépendances restent manquantes.");
      }
      setTimeout(() => bootstrapProgression.close(), 320);
      return payload;
    } catch (error) {
      appState.bootstrapReady = false;
      appState.bootstrapPromise = null;
      setSidebarRuntimeStatus("Packages incomplets (voir logs)", "error");
      log(`[error] Bootstrap impossible : ${error?.message || String(error)}`);
      bootstrapProgression.set(100, "Échec du bootstrap de démarrage.");
      setTimeout(() => bootstrapProgression.close(), 400);
      return { success: false, message: error?.message || String(error) };
    }
  })();

  return appState.bootstrapPromise;
}

function log(message) {
  logs.textContent += `\n${message}`;
  logs.scrollTop = logs.scrollHeight;
}

function activateTopTab(target) {
  topNavLinks.forEach((link) => {
    link.classList.toggle("is-active", link.dataset.tabTarget === target);
  });

  panels.forEach((panel) => {
    const isActive = panel.dataset.panel === target;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function activateChdSubTab(target) {
  chdSubNavLinks.forEach((link) => {
    link.classList.toggle("is-active", link.dataset.subtabTarget === target);
  });

  chdSubPanels.forEach((panel) => {
    const isActive = panel.dataset.subpanel === target;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function activateLdaSubTab(target) {
  ldaSubNavLinks.forEach((link) => {
    link.classList.toggle("is-active", link.dataset.ldaSubtabTarget === target);
  });

  ldaSubPanels.forEach((panel) => {
    const isActive = panel.dataset.ldaSubpanel === target;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function activateSuiviSubTab(target) {
  suiviSubNavLinks.forEach((link) => {
    link.classList.toggle("is-active", link.dataset.suiviSubtabTarget === target);
  });

  suiviSubPanels.forEach((panel) => {
    const isActive = panel.dataset.suiviSubpanel === target;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function activateMultimodalSubTab(target) {
  multimodalSubNavLinks.forEach((link) => {
    link.classList.toggle("is-active", link.dataset.multimodalSubtabTarget === target);
  });

  multimodalSubPanels.forEach((panel) => {
    const isActive = panel.dataset.multimodalSubpanel === target;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function activateMotionResultTab(target) {
  motionResultTabLinks.forEach((link) => {
    link.classList.toggle("is-active", link.dataset.motionResultTarget === target);
  });

  motionResultPanels.forEach((panel) => {
    const isActive = panel.dataset.motionResultPanel === target;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function revealMultimodalElement(element) {
  if (!(element instanceof HTMLElement)) return;
  window.setTimeout(() => {
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    try {
      element.focus({ preventScroll: true });
    } catch (_error) {
      // no-op
    }
  }, 60);
}

function activateHelpSubTab(target) {
  helpSubNavLinks.forEach((link) => {
    link.classList.toggle("is-active", link.dataset.helpSubtabTarget === target);
  });

  helpSubPanels.forEach((panel) => {
    const isActive = panel.dataset.helpSubpanel === target;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
}

function normalizePath(value) {
  return value.replace(/\\/g, "/").replace(/^\/+/, "").toLowerCase();
}

function getRelativePath(file) {
  const rawPath = file.virtualRelativePath || file.webkitRelativePath || file.name;
  const parts = rawPath.replace(/\\/g, "/").split("/");
  return parts.length > 1 ? parts.slice(1).join("/") : parts[0];
}

function getFileSizeLabel(file) {
  const sizeKo = Math.max(1, Math.round(file.size / 1024));
  return `${sizeKo} Ko`;
}

function getNativeFilePath(file) {
  if (!file) return "";
  return String(file.path || file.absolutePath || "").trim();
}

function getSelectedFile(input) {
  return input?.files?.[0] || null;
}

function getMultimodalPreparedPath(slot) {
  return String(appState.multimodalLocalPaths?.[slot] || "").trim();
}

function setMultimodalPreparedPath(slot, value) {
  if (!appState.multimodalLocalPaths) return;
  appState.multimodalLocalPaths[slot] = String(value || "").trim();
}

function isMultimodalInputPending(slot) {
  return Boolean(appState.multimodalPendingInputs?.[slot]);
}

function setMultimodalInputPending(slot, value) {
  if (!appState.multimodalPendingInputs) return;
  appState.multimodalPendingInputs[slot] = Boolean(value);
}

function getMultimodalInputError(slot) {
  return String(appState.multimodalInputErrors?.[slot] || "").trim();
}

function setMultimodalInputError(slot, value) {
  if (!appState.multimodalInputErrors) return;
  appState.multimodalInputErrors[slot] = String(value || "").trim();
}

function getResolvedMultimodalPath(slot, file) {
  return getNativeFilePath(file) || getMultimodalPreparedPath(slot);
}

function getMultimodalGeneratedPath(slot) {
  return String(appState.multimodalGeneratedPaths?.[slot] || "").trim();
}

function setMultimodalGeneratedPath(slot, value) {
  if (!appState.multimodalGeneratedPaths) return;
  appState.multimodalGeneratedPaths[slot] = String(value || "").trim();
}

function getMultimodalComparisonSourceState(side) {
  const normalizedSide = side === "b" ? "b" : "a";
  return appState.multimodalComparisonAB?.sources?.[normalizedSide] || null;
}

function getMultimodalComparisonSelectFaceButton(side) {
  return side === "b" ? multimodalCompareSelectFaceBBtn : multimodalCompareSelectFaceABtn;
}

function getMultimodalComparisonClearFaceButton(side) {
  return side === "b" ? multimodalCompareClearFaceBBtn : multimodalCompareClearFaceABtn;
}

function getMultimodalComparisonFaceStatusElement(side) {
  return side === "b" ? multimodalCompareFaceStatusB : multimodalCompareFaceStatusA;
}

function getMultimodalComparisonVideoInput(side) {
  return side === "b" ? multimodalCompareVideoFileB : multimodalCompareVideoFileA;
}

function getMultimodalComparisonStatusElement(side) {
  return side === "b" ? multimodalCompareSourceStatusB : multimodalCompareSourceStatusA;
}

function getMultimodalComparisonYoutubeUrl(side) {
  const input = side === "b" ? multimodalCompareYoutubeUrlB : multimodalCompareYoutubeUrlA;
  return String(input?.value || "").trim();
}

function getMultimodalComparisonVideoFile(side) {
  return getSelectedFile(getMultimodalComparisonVideoInput(side));
}

function getMultimodalComparisonPreparedVideoPath(side) {
  return String(getMultimodalComparisonSourceState(side)?.preparedVideoPath || "").trim();
}

function setMultimodalComparisonPreparedVideoPath(side, value) {
  const target = getMultimodalComparisonSourceState(side);
  if (!target) return;
  target.preparedVideoPath = String(value || "").trim();
}

function getMultimodalComparisonFaceSelection(side) {
  const selection = getMultimodalComparisonSourceState(side)?.selectedFaceSelection;
  return selection && Array.isArray(selection.box) && selection.box.length === 4 ? selection : null;
}

function setMultimodalComparisonFaceSelection(side, selection) {
  const target = getMultimodalComparisonSourceState(side);
  if (!target) return;
  target.selectedFaceSelection = selection && Array.isArray(selection.box) && selection.box.length === 4
    ? {
        sourceName: String(selection.sourceName || "").trim(),
        sourceIndex: Number.isInteger(Number(selection.sourceIndex)) ? Number(selection.sourceIndex) : 0,
        box: selection.box.map((value) => Number(value || 0)),
      }
    : null;
}

function clearMultimodalComparisonFaceSelection(side, { rerender = true } = {}) {
  setMultimodalComparisonFaceSelection(side, null);
  if (rerender) {
    renderMultimodalWorkspace();
  }
}

function getMultimodalComparisonLatestExtraction(side) {
  return getMultimodalComparisonSourceState(side)?.latestExtraction || null;
}

function setMultimodalComparisonLatestExtraction(side, extraction) {
  const target = getMultimodalComparisonSourceState(side);
  if (!target) return;
  target.latestExtraction = extraction || null;
}

function resetMultimodalComparisonSourceRuntime(side, { rerender = true } = {}) {
  clearMultimodalComparisonFaceSelection(side, { rerender: false });
  setMultimodalComparisonLatestExtraction(side, null);
  if (rerender) {
    renderMultimodalWorkspace();
  }
}

function getMultimodalComparisonError(side) {
  return String(getMultimodalComparisonSourceState(side)?.error || "").trim();
}

function setMultimodalComparisonError(side, value) {
  const target = getMultimodalComparisonSourceState(side);
  if (!target) return;
  target.error = String(value || "").trim();
}

function getResolvedMultimodalComparisonVideoPath(side, file) {
  return getNativeFilePath(file) || getMultimodalComparisonPreparedVideoPath(side);
}

function getMultimodalComparisonSource(side) {
  const videoFile = getMultimodalComparisonVideoFile(side);
  if (videoFile) {
    const videoPath = getResolvedMultimodalComparisonVideoPath(side, videoFile);
    return videoPath ? { kind: "video_file", value: videoPath } : null;
  }

  const preparedVideoPath = getMultimodalComparisonPreparedVideoPath(side);
  if (preparedVideoPath) {
    return { kind: "video_file", value: preparedVideoPath };
  }

  const youtubeUrl = getMultimodalComparisonYoutubeUrl(side);
  if (youtubeUrl) {
    return { kind: "youtube", value: youtubeUrl };
  }

  return null;
}

function getMultimodalComparisonLabel(side) {
  const normalizedSide = side === "b" ? "b" : "a";
  const videoFile = getMultimodalComparisonVideoFile(normalizedSide);
  if (videoFile?.name) {
    return String(videoFile.name).replace(/\.[^.]+$/, "") || `Vidéo ${normalizedSide.toUpperCase()}`;
  }

  const resolvedPath = getMultimodalComparisonPreparedVideoPath(normalizedSide);
  if (resolvedPath) {
    const parts = resolvedPath.split(/[\\/]/).filter(Boolean);
    const lastPart = parts.at(-1) || "";
    return lastPart.replace(/\.[^.]+$/, "") || `Vidéo ${normalizedSide.toUpperCase()}`;
  }

  const youtubeUrl = getMultimodalComparisonYoutubeUrl(normalizedSide);
  const youtubeId = extractYouTubeVideoId(youtubeUrl);
  if (youtubeId) {
    return `youtube-${youtubeId}`;
  }

  return `Vidéo ${normalizedSide.toUpperCase()}`;
}

function isMultimodalComparisonAbRunning() {
  return Boolean(appState.multimodalComparisonAB?.running);
}

function setMultimodalComparisonAbRunning(value) {
  if (!appState.multimodalComparisonAB) return;
  appState.multimodalComparisonAB.running = Boolean(value);
}

function isMultimodalComparisonAbSettingsOpen() {
  return Boolean(appState.multimodalComparisonAB?.settingsOpen);
}

function setMultimodalComparisonAbSettingsOpen(value) {
  if (!appState.multimodalComparisonAB) return;
  appState.multimodalComparisonAB.settingsOpen = Boolean(value);
}

function isMultimodalComparisonAbFullscreen() {
  return Boolean(appState.multimodalComparisonAB?.fullscreen);
}

function setMultimodalComparisonAbFullscreen(value) {
  if (!appState.multimodalComparisonAB) return;
  appState.multimodalComparisonAB.fullscreen = Boolean(value);
}

function getMultimodalComparisonBaseOutputDir() {
  return String(appState.multimodalComparisonAB?.outputDir || "").trim();
}

function getMultimodalComparisonFrameRateValue() {
  const rawValue = Number(multimodalCompareFrameRate?.value ?? 1);
  return rawValue >= 25 ? 25 : 1;
}

function getMultimodalComparisonTimeInputs(side) {
  if (side === "b") {
    return {
      startHours: multimodalCompareStartHoursB,
      startMinutes: multimodalCompareStartMinutesB,
      startSeconds: multimodalCompareStartSecondsB,
      endHours: multimodalCompareEndHoursB,
      endMinutes: multimodalCompareEndMinutesB,
      endSeconds: multimodalCompareEndSecondsB,
    };
  }
  return {
    startHours: multimodalCompareStartHoursA,
    startMinutes: multimodalCompareStartMinutesA,
    startSeconds: multimodalCompareStartSecondsA,
    endHours: multimodalCompareEndHoursA,
    endMinutes: multimodalCompareEndMinutesA,
    endSeconds: multimodalCompareEndSecondsA,
  };
}

function hasAnyHmsValue({ hours, minutes, seconds } = {}) {
  return [hours, minutes, seconds].some((value) => String(value ?? "").trim() !== "");
}

function getMultimodalComparisonStartSec(side) {
  const inputs = getMultimodalComparisonTimeInputs(side);
  const hasStart = hasAnyHmsValue({
    hours: inputs.startHours?.value,
    minutes: inputs.startMinutes?.value,
    seconds: inputs.startSeconds?.value,
  });
  const hasEnd = hasAnyHmsValue({
    hours: inputs.endHours?.value,
    minutes: inputs.endMinutes?.value,
    seconds: inputs.endSeconds?.value,
  });
  if (!hasStart && !hasEnd) return null;
  return buildSecondsFromHms({
    hours: inputs.startHours?.value,
    minutes: inputs.startMinutes?.value,
    seconds: inputs.startSeconds?.value,
    defaultToZero: true,
  });
}

function getMultimodalComparisonEndSec(side) {
  const inputs = getMultimodalComparisonTimeInputs(side);
  const hasEnd = hasAnyHmsValue({
    hours: inputs.endHours?.value,
    minutes: inputs.endMinutes?.value,
    seconds: inputs.endSeconds?.value,
  });
  if (!hasEnd) return null;
  return buildSecondsFromHms({
    hours: inputs.endHours?.value,
    minutes: inputs.endMinutes?.value,
    seconds: inputs.endSeconds?.value,
    defaultToZero: false,
  });
}

function getMultimodalComparisonOutputDir() {
  const comparisonDir = getMultimodalComparisonBaseOutputDir();
  if (comparisonDir) {
    return comparisonDir.replace(/[\\/]+$/, "");
  }
  return `${getMultimodalOutputDir("comparaison_ab")}`;
}

function buildMultimodalComparisonCaseDirs(side) {
  const normalizedSide = side === "b" ? "b" : "a";
  const caseRoot = `${getMultimodalComparisonOutputDir()}/video_${normalizedSide}`;
  return {
    root: caseRoot,
    extraction: `${caseRoot}/extraction`,
    audio: `${caseRoot}/audio`,
    mouvements: `${caseRoot}/mouvements`,
    alignement: `${caseRoot}/alignement`,
  };
}

function findMultimodalResponsePath(response, predicate) {
  if (!response?.outputDir || !Array.isArray(response.files)) return "";
  const match = response.files.find((file) => predicate(String(file?.relativePath || "").replace(/\\/g, "/")));
  if (!match?.relativePath) return "";
  const baseDir = String(response.outputDir).replace(/[\\/]+$/, "");
  const relativePath = String(match.relativePath).replace(/^[/\\]+/, "").replace(/\\/g, "/");
  return `${baseDir}/${relativePath}`;
}

function findMultimodalResponseArtifact(response, predicate) {
  if (!Array.isArray(response?.files)) return null;
  return response.files.find((file) => predicate(String(file?.relativePath || "").replace(/\\/g, "/"))) || null;
}

function hydrateGeneratedMultimodalAssets(scriptName, response) {
  if (!response?.outputDir) return;

  if (scriptName === "alignement.py") {
    const preparedVideo = findMultimodalResponsePath(response, (path) => path.endsWith("downloads/source_video.mp4"));
    const preparedAudioMp3 = findMultimodalResponsePath(response, (path) => path.endsWith("audio/audio_source.mp3"));
    const preparedAudioWav = findMultimodalResponsePath(response, (path) => path.endsWith("audio/audio_source.wav"));
    const framesIndex = findMultimodalResponsePath(response, (path) => path.endsWith("frames_index.csv"));
    const sampleFrame = findMultimodalResponsePath(response, (path) => path.includes("/frames/") && /\.(png|jpe?g|bmp|webp)$/i.test(path));
    const alignmentCsv =
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_images_alignement.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_images_alignment.csv"));
    const alignedSegmentsCsv = findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_sync.csv"));
    const timelineJson = findMultimodalResponsePath(response, (path) => path.endsWith("timeline_multimodale.json"));
    if (preparedVideo) setMultimodalGeneratedPath("video", preparedVideo);
    if (preparedAudioMp3 || preparedAudioWav) {
      setMultimodalGeneratedPath("audio", preparedAudioMp3 || preparedAudioWav);
    }
    if (framesIndex) setMultimodalGeneratedPath("framesIndex", framesIndex);
    if (sampleFrame) {
      setMultimodalGeneratedPath("framesDir", sampleFrame.replace(/[/\\][^/\\]+$/, ""));
    }
    if (alignmentCsv) setMultimodalGeneratedPath("alignmentCsv", alignmentCsv);
    if (alignedSegmentsCsv) setMultimodalGeneratedPath("segmentsAligned", alignedSegmentsCsv);
    appState.multimodalResults.alignement = {
      outputDir: response.outputDir,
      files: Array.isArray(response.files) ? response.files : [],
      videoPath: preparedVideo,
      audioPath: preparedAudioMp3 || preparedAudioWav,
      audioMp3Path: preparedAudioMp3,
      audioWavPath: preparedAudioWav,
      framesDirPath: sampleFrame ? sampleFrame.replace(/[/\\][^/\\]+$/, "") : "",
      framesIndexPath: framesIndex,
      alignmentCsvPath: alignmentCsv,
      alignmentCsvArtifact:
        findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_images_alignement.csv")) ||
        findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_images_alignment.csv")),
      alignedSegmentsCsvPath: alignedSegmentsCsv,
      alignedSegmentsCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_sync.csv")),
      timelineJsonPath: timelineJson,
      timelineJsonArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("timeline_multimodale.json"))
    };
    appState.multimodalResults.segments = appState.multimodalResults.alignement;
  }

  if (scriptName === "audio.py") {
    const segmentsCsv =
      findMultimodalResponsePath(response, (path) => path.endsWith("transcription_segments_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("transcription_segments.csv"));
    const segmentsGlobalCsv =
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_global_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_global.csv"));
    const segmentsAnomaliesCsv =
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_anomalies_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_anomalies.csv"));
    const summaryJson = findMultimodalResponsePath(response, (path) => path.endsWith("audio_summary.json"));
    const segmentsTxt = findMultimodalResponsePath(response, (path) => path.endsWith("transcription_segments_timestamped.txt"));
    const segmentsGlobalTxt = findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_global_timestamped.txt"));
    const pausesCsv =
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_pauses_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_pauses.csv"));
    const pausesPng = findMultimodalResponsePath(response, (path) => path.endsWith("audio_pauses_altair.png"));
    const speechRatePng = findMultimodalResponsePath(response, (path) => path.endsWith("audio_speech_rate_altair.png"));
    const anomaliesPng = findMultimodalResponsePath(response, (path) => path.endsWith("audio_anomalies_altair.png"));
    const anomaliesCsv =
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_anomalies_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_anomalies.csv"));
    const anomaliesConcordancierCsv =
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_anomalies_concordancier_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_anomalies_concordancier.csv"));
    if (segmentsGlobalCsv || segmentsCsv) {
      setMultimodalGeneratedPath("segments", segmentsGlobalCsv || segmentsCsv);
    }
    appState.multimodalResults.audio = {
      outputDir: response.outputDir,
      segmentsCsvPath: segmentsCsv,
      segmentsGlobalCsvPath: segmentsGlobalCsv,
      segmentsAnomaliesCsvPath: segmentsAnomaliesCsv,
      summaryJsonPath: summaryJson,
      segmentsTxtPath: segmentsTxt,
      segmentsGlobalTxtPath: segmentsGlobalTxt,
      pausesCsvPath: pausesCsv,
      pausesPngPath: pausesPng,
      speechRatePngPath: speechRatePng,
      anomaliesPngPath: anomaliesPng,
      anomaliesCsvPath: anomaliesCsv,
      anomaliesConcordancierCsvPath: anomaliesConcordancierCsv,
      segmentsCsvArtifact:
        findMultimodalResponseArtifact(response, (path) => path.endsWith("transcription_segments_complet.csv")) ||
        findMultimodalResponseArtifact(response, (path) => path.endsWith("transcription_segments.csv")),
      segmentsGlobalCsvArtifact:
        findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_global_complet.csv")) ||
        findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_global.csv")),
      segmentsAnomaliesCsvArtifact:
        findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_anomalies_complet.csv")) ||
        findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_anomalies.csv")),
      summaryJsonArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_summary.json")),
      segmentsTxtArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("transcription_segments_timestamped.txt")),
      segmentsGlobalTxtArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_global_timestamped.txt")),
      pausesCsvArtifact:
        findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_pauses_complet.csv")) ||
        findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_pauses.csv")),
      pausesPngArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_pauses_altair.png")),
      speechRatePngArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_speech_rate_altair.png")),
      anomaliesPngArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_anomalies_altair.png")),
      anomaliesCsvArtifact:
        findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_anomalies_complet.csv")) ||
        findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_anomalies.csv")),
      anomaliesConcordancierCsvArtifact:
        findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_anomalies_concordancier_complet.csv")) ||
        findMultimodalResponseArtifact(response, (path) => path.endsWith("audio_anomalies_concordancier.csv"))
    };
  }

  if (scriptName === "mouvements.py") {
    const framesCsv = findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_frames.csv"));
    const multifaceCsv = findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_multivisage.csv"));
    const windowsCsv = findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_windows.csv"));
    const summaryJson = findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_summary.json"));
    const heatmapPng = findMultimodalResponsePath(response, (path) => path.endsWith("motion_heatmap.png"));
    const chartPng = findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_timeline_altair.png"));
    appState.multimodalResults.mouvements = {
      outputDir: response.outputDir,
      framesCsvPath: framesCsv,
      multifaceCsvPath: multifaceCsv,
      windowsCsvPath: windowsCsv,
      summaryJsonPath: summaryJson,
      heatmapPngPath: heatmapPng,
      chartPngPath: chartPng,
      artifacts: Array.isArray(response.files) ? response.files : [],
      framesCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("mouvements_frames.csv")),
      multifaceCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("mouvements_multivisage.csv")),
      windowsCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("mouvements_windows.csv")),
      summaryJsonArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("mouvements_summary.json")),
      heatmapPngArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("motion_heatmap.png")),
      chartPngArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("mouvements_timeline_altair.png"))
    };
  }

  if (scriptName === "noeuds.py") {
    const graphJson = findMultimodalResponsePath(response, (path) => path.endsWith("noeuds_graphe.json"));
    const summaryJson = findMultimodalResponsePath(response, (path) => path.endsWith("noeuds_summary.json"));
    const nodesCsv = findMultimodalResponsePath(response, (path) => path.endsWith("noeuds_noeuds.csv"));
    const edgesCsv = findMultimodalResponsePath(response, (path) => path.endsWith("noeuds_liens.csv"));
    appState.multimodalResults.noeuds = {
      outputDir: response.outputDir,
      graphJsonPath: graphJson,
      summaryJsonPath: summaryJson,
      nodesCsvPath: nodesCsv,
      edgesCsvPath: edgesCsv,
      graphJsonArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("noeuds_graphe.json")),
      summaryJsonArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("noeuds_summary.json")),
      nodesCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("noeuds_noeuds.csv")),
      edgesCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("noeuds_liens.csv")),
    };
  }
}

function getMultimodalComparisonExtractionArtifacts(response) {
  const preparedVideo = findMultimodalResponsePath(response, (path) => path.endsWith("downloads/source_video.mp4"));
  const preparedAudioMp3 = findMultimodalResponsePath(response, (path) => path.endsWith("audio/audio_source.mp3"));
  const preparedAudioWav = findMultimodalResponsePath(response, (path) => path.endsWith("audio/audio_source.wav"));
  const framesIndex = findMultimodalResponsePath(response, (path) => path.endsWith("frames_index.csv"));
  const sampleFrame = findMultimodalResponsePath(
    response,
    (path) => /(^|\/)frames\/.+\.(png|jpe?g|bmp|webp)$/i.test(String(path || "").replace(/\\/g, "/"))
  );
  const outputDir = String(response?.outputDir || "").trim();
  const framesDirFallback = outputDir ? `${outputDir.replace(/[\\/]+$/, "")}/frames` : "";
  return {
    outputDir,
    videoPath: preparedVideo,
    audioMp3Path: preparedAudioMp3,
    audioWavPath: preparedAudioWav,
    audioPath: preparedAudioMp3 || preparedAudioWav,
    framesIndexPath: framesIndex,
    framesIndexArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("frames_index.csv")),
    framesDirPath: sampleFrame ? sampleFrame.replace(/[/\\][^/\\]+$/, "") : framesDirFallback,
    artifacts: Array.isArray(response.files) ? response.files : [],
  };
}

function buildMultimodalComparisonFaceSelectionSources(side, extractionArtifacts = getMultimodalComparisonLatestExtraction(side)) {
  const outputDir = String(extractionArtifacts?.outputDir || "").trim().replace(/[\\/]+$/, "");
  const artifacts = Array.isArray(extractionArtifacts?.artifacts) ? extractionArtifacts.artifacts : [];
  const frameArtifacts = artifacts
    .filter((artifact) => {
      const relativePath = String(artifact?.relativePath || "").replace(/\\/g, "/");
      return /(^|\/)frames\/.+\.(png|jpe?g|bmp|webp)$/i.test(relativePath);
    })
    .map((artifact) => {
      const relativePath = String(artifact.relativePath || "").replace(/^[/\\]+/, "").replace(/\\/g, "/");
      const filename = relativePath.split("/").pop() || `frame_${side}`;
      return {
        name: filename,
        sourceName: filename,
        absolutePath: outputDir ? `${outputDir}/${relativePath}` : "",
        artifact,
      };
    })
    .sort((left, right) => naturalCompareValues(left.name || "", right.name || ""))
    .map((sourceItem, index) => ({
      ...sourceItem,
      sourceIndex: index,
    }));

  if (frameArtifacts.length) {
    return frameArtifacts;
  }

  const framesIndexArtifact = extractionArtifacts?.framesIndexArtifact || null;
  if (!framesIndexArtifact) {
    return [];
  }

  return rowsFromParsedCsv(parseCsv(artifactDataToText(framesIndexArtifact)))
    .map((row, index) => {
      const framePath = String(row?.frame_path || "").trim();
      const filename = framePath.split(/[\\/]/).pop() || `frame_${side}_${index + 1}`;
      return {
        name: filename,
        sourceName: filename,
        absolutePath: framePath,
        sourceIndex: index,
      };
    })
    .filter((item) => item.absolutePath)
    .sort((left, right) => naturalCompareValues(left.name || "", right.name || ""))
    .map((sourceItem, index) => ({
      ...sourceItem,
      sourceIndex: index,
    }));
}

function hasValidMultimodalComparisonFaceSelection(side, sourceItems = buildMultimodalComparisonFaceSelectionSources(side)) {
  const selection = getMultimodalComparisonFaceSelection(side);
  if (!selection || !sourceItems.length) return false;
  const index = Number(selection.sourceIndex);
  if (!Number.isInteger(index) || index < 0 || index >= sourceItems.length) return false;
  const sourceItem = sourceItems[index];
  return String(selection.sourceName || "").trim() === String(sourceItem?.sourceName || sourceItem?.name || "").trim();
}

function updateMultimodalComparisonFaceSelectionStatus(side) {
  const statusElement = getMultimodalComparisonFaceStatusElement(side);
  if (!statusElement) return;
  const isBodyMode = multimodalMotionAnatomyMode?.value === "corps_entier";
  const isManualMode = multimodalMotionFaceAnalysisMode?.value === "manuel";
  const sourceItems = buildMultimodalComparisonFaceSelectionSources(side);
  const source = getMultimodalComparisonSource(side);
  const selection = getMultimodalComparisonFaceSelection(side);
  const sideLabel = side === "b" ? "B" : "A";

  if (isBodyMode) {
    setReadonlyStatus(statusElement, `La sélection manuelle ${sideLabel} est disponible uniquement en mode visage.`);
    return;
  }
  if (!isManualMode) {
    setReadonlyStatus(statusElement, `Active « sélection à la souris » pour choisir un visage ${sideLabel}.`);
    return;
  }
  if (!sourceItems.length) {
    if (source?.value) {
      setReadonlyStatus(statusElement, `Clique sur « Sélectionner le visage ${sideLabel} » pour préparer les images de référence puis choisir le visage.`);
    } else {
      setReadonlyStatus(statusElement, `Renseigne d'abord une source ${sideLabel} pour pouvoir sélectionner un visage.`);
    }
    return;
  }
  if (!selection || !hasValidMultimodalComparisonFaceSelection(side, sourceItems)) {
    setReadonlyStatus(statusElement, `Aucune sélection manuelle enregistrée pour ${sideLabel}.`);
    return;
  }

  const sourceName = String(selection.sourceName || sourceItems[0]?.name || "image").trim();
  const sourceIndex = Number.isInteger(Number(selection.sourceIndex)) ? Number(selection.sourceIndex) : 0;
  setReadonlyStatus(
    statusElement,
    `Visage ${sideLabel} sélectionné sur ${sourceName} (image ${sourceIndex + 1}/${Math.max(1, sourceItems.length)}). Point de départ du suivi : ${formatNormalizedFaceSelection(selection.box)}.`
  );
}

async function ensureMultimodalComparisonFaceSelectionSources(side) {
  const normalizedSide = side === "b" ? "b" : "a";
  const existingSources = buildMultimodalComparisonFaceSelectionSources(normalizedSide);
  if (existingSources.length) {
    return existingSources;
  }

  const extractionRequest = buildMultimodalComparisonExtractionRequest(normalizedSide);
  if (!extractionRequest) {
    return [];
  }

  const sideLabel = normalizedSide === "b" ? "B" : "A";
  const label = getMultimodalComparisonLabel(normalizedSide);
  const extractionResponse = await runMultimodalScript(extractionRequest, {
    title: `Sélection du visage ${sideLabel}`,
    message: `Extraction des images de référence pour ${label}...`,
    statusElement: getMultimodalComparisonFaceStatusElement(normalizedSide),
    actionButton: getMultimodalComparisonSelectFaceButton(normalizedSide),
    hydrateAssets: false,
    recordHistory: false,
    plannedStages: [
      `Préparation de la source ${sideLabel}...`,
      `Extraction des images ${sideLabel}...`,
      `Préparation de la sélection du visage ${sideLabel}...`,
    ],
  });
  if (!extractionResponse) {
    return [];
  }

  const extractionArtifacts = getMultimodalComparisonExtractionArtifacts(extractionResponse);
  setMultimodalComparisonLatestExtraction(normalizedSide, extractionArtifacts);
  renderMultimodalWorkspace();
  return buildMultimodalComparisonFaceSelectionSources(normalizedSide, extractionArtifacts);
}

async function openMultimodalComparisonFaceSelectionDialog(side) {
  const normalizedSide = side === "b" ? "b" : "a";
  const sourceItems = await ensureMultimodalComparisonFaceSelectionSources(normalizedSide);
  const sideLabel = normalizedSide === "b" ? "B" : "A";
  if (!sourceItems.length) {
    setReadonlyStatus(
      getMultimodalComparisonFaceStatusElement(normalizedSide),
      `Impossible de sélectionner le visage ${sideLabel} : aucune image de référence n'a pu être préparée.`,
      { isError: true }
    );
    return;
  }
  openMultimodalFaceSelectionDialogSession({
    sources: sourceItems,
    selection: getMultimodalComparisonFaceSelection(normalizedSide),
    onSave(selection) {
      setMultimodalComparisonFaceSelection(normalizedSide, selection);
      renderMultimodalWorkspace();
    },
    onClose() {
      renderMultimodalWorkspace();
    },
  });
}

async function ensureMultimodalComparisonFaceSelection(side, extractionArtifacts, label) {
  const normalizedSide = side === "b" ? "b" : "a";
  const sourceItems = buildMultimodalComparisonFaceSelectionSources(normalizedSide, extractionArtifacts);
  const sideLabel = normalizedSide === "b" ? "B" : "A";
  if (!sourceItems.length) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Impossible de préparer la sélection du visage pour la vidéo ${sideLabel} : aucune image extraite n'est disponible.`,
      { isError: true }
    );
    return false;
  }
  if (hasValidMultimodalComparisonFaceSelection(normalizedSide, sourceItems)) {
    return true;
  }
  setReadonlyStatus(
    multimodalCompareAbRunStatus,
    `Sélectionne le visage à suivre pour ${label}, puis valide la boîte de dialogue pour poursuivre.`,
  );
  return new Promise((resolve) => {
    openMultimodalFaceSelectionDialogSession({
      sources: sourceItems,
      selection: getMultimodalComparisonFaceSelection(normalizedSide),
      onSave(selection) {
        setMultimodalComparisonFaceSelection(normalizedSide, selection);
        renderMultimodalWorkspace();
        resolve(true);
      },
      onClose() {
        renderMultimodalWorkspace();
        resolve(false);
      },
    });
  });
}

function getMultimodalComparisonAudioArtifacts(response) {
  return {
    outputDir: response.outputDir,
    segmentsCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("transcription_segments_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("transcription_segments.csv")),
    segmentsGlobalCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_global_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_global.csv")),
    anomaliesCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_anomalies_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_anomalies.csv")),
    pausesCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_pauses_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("audio_pauses.csv")),
    summaryJsonPath: findMultimodalResponsePath(response, (path) => path.endsWith("audio_summary.json")),
    artifacts: Array.isArray(response.files) ? response.files : [],
  };
}

function getMultimodalComparisonMotionArtifacts(response) {
  return {
    outputDir: response.outputDir,
    framesCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_frames_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_frames.csv")),
    windowsCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_windows_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_windows.csv")),
    summaryJsonPath: findMultimodalResponsePath(response, (path) => path.endsWith("mouvements_summary.json")),
    artifacts: Array.isArray(response.files) ? response.files : [],
  };
}

function getMultimodalComparisonAlignmentArtifacts(response) {
  return {
    outputDir: response.outputDir,
    alignedSegmentsCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_sync_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_texte_sync.csv")),
    alignedSegmentsCsvArtifact:
      findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_sync_complet.csv")) ||
      findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_texte_sync.csv")),
    alignmentCsvPath:
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_images_alignement_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_images_alignement.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_images_alignment_complet.csv")) ||
      findMultimodalResponsePath(response, (path) => path.endsWith("segments_images_alignment.csv")),
    alignmentCsvArtifact:
      findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_images_alignement_complet.csv")) ||
      findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_images_alignement.csv")) ||
      findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_images_alignment_complet.csv")) ||
      findMultimodalResponseArtifact(response, (path) => path.endsWith("segments_images_alignment.csv")),
    timelineJsonPath: findMultimodalResponsePath(response, (path) => path.endsWith("timeline_multimodale.json")),
    timelineJsonArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("timeline_multimodale.json")),
    artifacts: Array.isArray(response.files) ? response.files : [],
  };
}

function hydrateMultimodalComparisonAbAssets(response, context = {}) {
  if (!appState.multimodalComparisonAB) return;
  appState.multimodalComparisonAB.result = {
    outputDir: response?.outputDir || "",
    summaryJsonPath: findMultimodalResponsePath(response, (path) => path.endsWith("comparaison_ab_summary.json")),
    timelineCsvPath: findMultimodalResponsePath(response, (path) => path.endsWith("comparaison_ab_timeline.csv")),
    indicatorsCsvPath: findMultimodalResponsePath(response, (path) => path.endsWith("comparaison_ab_indicateurs.csv")),
    timelineTxtPath: findMultimodalResponsePath(response, (path) => path.endsWith("comparaison_ab_timeline_timestamped.txt")),
    segmentsTxtAPath: findMultimodalResponsePath(response, (path) => path.endsWith("video_a_segments_timestamped.txt")),
    segmentsTxtBPath: findMultimodalResponsePath(response, (path) => path.endsWith("video_b_segments_timestamped.txt")),
    summaryJsonArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("comparaison_ab_summary.json")),
    timelineCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("comparaison_ab_timeline.csv")),
    indicatorsCsvArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("comparaison_ab_indicateurs.csv")),
    timelineTxtArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("comparaison_ab_timeline_timestamped.txt")),
    segmentsTxtAArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("video_a_segments_timestamped.txt")),
    segmentsTxtBArtifact: findMultimodalResponseArtifact(response, (path) => path.endsWith("video_b_segments_timestamped.txt")),
    files: Array.isArray(response?.files) ? response.files : [],
    caseA: context.caseA || null,
    caseB: context.caseB || null,
  };
}

function getMultimodalBaseOutputDir() {
  return String(appState.multimodalOutputDir || "").trim();
}

function getMultimodalOutputDir(subdir) {
  const baseDir = getMultimodalBaseOutputDir();
  if (!baseDir) {
    return `multimodale/exports/${subdir}`;
  }
  return `${baseDir.replace(/[\\/]+$/, "")}/${subdir}`;
}

function setCommandPreview(previewElement, buttonElement, command, emptyMessage) {
  if (!previewElement) return;
  const safeCommand = String(command || "").trim();
  previewElement.textContent = safeCommand || emptyMessage;
  previewElement.dataset.command = safeCommand;
  if (buttonElement) {
    buttonElement.disabled = !safeCommand;
    buttonElement.dataset.command = safeCommand;
  }
}

function setReadonlyStatus(element, message, { isError = false } = {}) {
  if (!element) return;
  element.textContent = message;
  element.classList.toggle("is-error", isError);
}

function formatSelectedFileStatus(file, emptyMessage, { preparedPath = "", pending = false } = {}) {
  if (!file) return emptyMessage;
  if (pending) {
    return `Préparation locale en cours pour ${file.name || "le fichier sélectionné"}...`;
  }
  const nativePath = getNativeFilePath(file);
  const label = nativePath || file.name || "Fichier sélectionné";
  if (preparedPath && !nativePath) {
    return `${label} (${getFileSizeLabel(file)}) · copie locale prête`;
  }
  return `${label} (${getFileSizeLabel(file)})`;
}

function getArchiveBaseName() {
  const rawName = String(appState.corpusFileName || "").trim();
  if (rawName) {
    return rawName.replace(/\.[^.]+$/, "") || rawName;
  }
  return appState.exportsFolderName || "iramuteq-resultats";
}

function getMultimodalYoutubeUrl() {
  return String(multimodalYoutubeUrl?.value || "").trim();
}

function extractYouTubeVideoId(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";

  try {
    const parsed = new URL(raw);
    const host = parsed.hostname.replace(/^www\./i, "").toLowerCase();
    if (host === "youtu.be") {
      const id = parsed.pathname.replace(/^\/+/, "").split("/")[0];
      return /^[A-Za-z0-9_-]{6,}$/.test(id) ? id : "";
    }
    if (host === "youtube.com" || host.endsWith(".youtube.com")) {
      const watchId = parsed.searchParams.get("v");
      if (watchId && /^[A-Za-z0-9_-]{6,}$/.test(watchId)) {
        return watchId;
      }
      const pathParts = parsed.pathname.split("/").filter(Boolean);
      const candidate = pathParts.length >= 2 && ["embed", "shorts", "live"].includes(pathParts[0])
        ? pathParts[1]
        : "";
      return /^[A-Za-z0-9_-]{6,}$/.test(candidate) ? candidate : "";
    }
  } catch (_error) {
    return "";
  }

  return "";
}

function getMultimodalCookiesFile() {
  return getSelectedFile(multimodalCookiesFile);
}

function getMultimodalAudioFile() {
  return getSelectedFile(multimodalAudioFile);
}

function getMultimodalVideoFile() {
  return getSelectedFile(multimodalVideoFile);
}

function getMultimodalCookiesPath() {
  const file = getMultimodalCookiesFile();
  return getResolvedMultimodalPath("cookies", file);
}

function getMultimodalAudioPath() {
  const file = getMultimodalAudioFile();
  return getResolvedMultimodalPath("audio", file) || getMultimodalGeneratedPath("audio");
}

function getMultimodalVideoPath() {
  const file = getMultimodalVideoFile();
  return getResolvedMultimodalPath("video", file) || getMultimodalGeneratedPath("video");
}

function naturalCompareValues(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, {
    numeric: true,
    sensitivity: "base"
  });
}

function getSelectedMultimodalImageFiles() {
  const selectedFiles = Array.isArray(appState.multimodalSelectedImageFiles)
    ? appState.multimodalSelectedImageFiles
    : [];
  const sourceFiles = selectedFiles.length ? selectedFiles : Array.from(multimodalImagesFiles?.files || []);
  return [...sourceFiles].sort((left, right) =>
    naturalCompareValues(left?.name || "", right?.name || "")
  );
}

function getMultimodalImagesDir() {
  return String(appState.multimodalLocalPaths?.imagesDir || "").trim() || getMultimodalGeneratedPath("framesDir");
}

function getMultimodalImagePaths() {
  return Array.isArray(appState.multimodalImagePaths) ? appState.multimodalImagePaths.filter(Boolean) : [];
}

function shouldPrepareMultimodalMp4() {
  return Boolean(multimodalExtractMp4?.checked);
}

function shouldPrepareMultimodalMp3() {
  return Boolean(multimodalExtractMp3?.checked);
}

function shouldPrepareMultimodalWav() {
  return Boolean(multimodalExtractWav?.checked);
}

function shouldPrepareMultimodalTimestampedSegments() {
  return Boolean(multimodalExtractSegments?.checked);
}

function shouldPrepareMultimodalImages() {
  return Boolean(multimodalExtractImages?.checked);
}

function hasSelectedMultimodalPreparationOutputs() {
  return (
    shouldPrepareMultimodalMp4() ||
    shouldPrepareMultimodalMp3() ||
    shouldPrepareMultimodalWav() ||
    shouldPrepareMultimodalTimestampedSegments() ||
    shouldPrepareMultimodalImages()
  );
}

function getMultimodalPreparationSource() {
  const videoFile = getMultimodalVideoFile();
  if (videoFile) {
    const videoPath = getMultimodalVideoPath();
    return videoPath ? { kind: "video_file", value: videoPath } : null;
  }

  const youtubeUrl = getMultimodalYoutubeUrl();
  if (youtubeUrl) {
    return { kind: "youtube", value: youtubeUrl };
  }

  return null;
}

function buildMultimodalYtdlpArgs() {
  const source = getMultimodalPreparationSource();
  const hasRequestedSourceOutputs =
    shouldPrepareMultimodalMp4() ||
    shouldPrepareMultimodalMp3() ||
    shouldPrepareMultimodalWav() ||
    shouldPrepareMultimodalImages();
  if (!source?.value || !hasRequestedSourceOutputs) return null;

  const cookiesFile = getMultimodalCookiesFile();
  const cookiesPath = getMultimodalCookiesPath();
  if (source.kind === "youtube" && cookiesFile && !cookiesPath) return null;
  const startSec = getMultimodalStartSec();
  const endSec = getMultimodalEndSec();
  const args = [
    "--source",
    source.value,
    "--output-dir",
    getMultimodalOutputDir("alignement"),
  ];
  if (source.kind === "youtube" && cookiesPath) {
    args.push("--cookies", cookiesPath);
  }
  if (startSec !== null) {
    args.push("--start-sec", String(startSec));
  }
  if (endSec !== null) {
    args.push("--end-sec", String(endSec));
  }
  if (shouldPrepareMultimodalMp4()) {
    args.push("--extract-mp4");
  }
  if (shouldPrepareMultimodalMp3()) {
    args.push("--extract-mp3");
  }
  if (shouldPrepareMultimodalWav()) {
    args.push("--extract-wav");
  }
  if (shouldPrepareMultimodalImages()) {
    args.push("--extract-frames", "--fps", String(getMultimodalFrameRateValue()), "--quality", getMultimodalFrameQualityValue());
  }
  return {
    scriptName: "alignement.py",
    args,
    outputDir: getMultimodalOutputDir("alignement"),
  };
}

function getPreferredAudioSource() {
  const audioFile = getMultimodalAudioFile();
  if (audioFile) {
    const audioPath = getMultimodalAudioPath();
    return audioPath ? { kind: "audio_file", value: audioPath } : null;
  }

  const preparedAudioPath = getMultimodalAudioPath();
  if (preparedAudioPath) {
    return { kind: "audio_file", value: preparedAudioPath };
  }

  const videoFile = getMultimodalVideoFile();
  if (videoFile) {
    const videoPath = getMultimodalVideoPath();
    return videoPath ? { kind: "video_file", value: videoPath } : null;
  }

  const preparedVideoPath = getMultimodalVideoPath();
  if (preparedVideoPath) {
    return { kind: "video_file", value: preparedVideoPath };
  }

  const youtubeUrl = getMultimodalYoutubeUrl();
  if (youtubeUrl) {
    return { kind: "youtube", value: youtubeUrl };
  }

  return null;
}

function getPreferredMotionSource() {
  const imagesDir = getMultimodalImagesDir();
  if (imagesDir) {
    return { kind: "images_dir", value: imagesDir };
  }

  return null;
}

function getPreferredAlignmentSource() {
  const imagesDir = getMultimodalImagesDir();
  if (imagesDir) {
    return { kind: "images_dir", value: imagesDir };
  }

  const videoFile = getMultimodalVideoFile();
  if (videoFile) {
    const videoPath = getMultimodalVideoPath();
    return videoPath ? { kind: "video_file", value: videoPath } : null;
  }

  const preparedVideoPath = getMultimodalVideoPath();
  if (preparedVideoPath) {
    return { kind: "video_file", value: preparedVideoPath };
  }

  const youtubeUrl = getMultimodalYoutubeUrl();
  if (youtubeUrl) {
    return { kind: "youtube", value: youtubeUrl };
  }

  return null;
}

function getSelectedMultimodalSegmentsFile() {
  return getSelectedFile(multimodalSegmentsFile);
}

function parsedToRowObjects(parsed) {
  if (!parsed?.headers?.length || !Array.isArray(parsed.rows)) {
    return [];
  }
  return parsed.rows.map((row) =>
    Object.fromEntries(parsed.headers.map((header, index) => [header, row[index] ?? ""]))
  );
}

function rowObjectsToParsed(rows) {
  if (!Array.isArray(rows) || !rows.length) {
    return { headers: [], rows: [] };
  }
  const headers = Array.from(
    rows.reduce((set, row) => {
      Object.keys(row || {}).forEach((key) => set.add(key));
      return set;
    }, new Set())
  );
  return {
    headers,
    rows: rows.map((row) => headers.map((header) => row?.[header] ?? "")),
  };
}

function isValidAlignmentSegmentsParsed(parsed) {
  const headers = Array.isArray(parsed?.headers)
    ? parsed.headers.map((header) => String(header || "").trim().toLowerCase())
    : [];
  return ["start_sec", "end_sec", "text"].every((requiredHeader) => headers.includes(requiredHeader));
}

function isAnomalyOnlySegmentsFile(file) {
  const name = String(file?.name || "").trim().toLowerCase();
  return name.includes("segments_texte_anomalies");
}

function isValidAlignmentSegmentsSelection(file, parsed) {
  return Boolean(file) && isValidAlignmentSegmentsParsed(parsed) && !isAnomalyOnlySegmentsFile(file);
}

function isAlignmentAudioOverlayEnabled() {
  return Boolean(multimodalAlignOverlayAudio?.checked);
}

function getMultimodalSegmentsPath() {
  const selectedFile = getSelectedMultimodalSegmentsFile();
  if (
    selectedFile &&
    appState.multimodalSegmentsPreviewParsed?.headers?.length &&
    isValidAlignmentSegmentsSelection(selectedFile, appState.multimodalSegmentsPreviewParsed)
  ) {
    return getResolvedMultimodalPath("segments", selectedFile);
  }
  return getMultimodalGeneratedPath("segments");
}

function getMultimodalMotionFramesCsvPath() {
  return String(appState.multimodalResults?.mouvements?.framesCsvPath || "").trim();
}

function getMultimodalAudioAnomaliesCsvPath() {
  return String(appState.multimodalResults?.audio?.anomaliesCsvPath || "").trim();
}

function getMultimodalAudioPausesCsvPath() {
  return String(appState.multimodalResults?.audio?.pausesCsvPath || "").trim();
}

async function persistSelectedMultimodalFile(slot, input, statusElement) {
  const file = getSelectedFile(input);
  setMultimodalInputError(slot, "");

  if (!file) {
    setMultimodalPreparedPath(slot, "");
    setMultimodalInputPending(slot, false);
    renderMultimodalWorkspace();
    return "";
  }

  const nativePath = getNativeFilePath(file);
  if (nativePath) {
    setMultimodalPreparedPath(slot, nativePath);
    setMultimodalInputPending(slot, false);
    renderMultimodalWorkspace();
    return nativePath;
  }

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    const message = `Impossible de préparer ${file.name || "ce fichier"} hors de l'application Tauri.`;
    setMultimodalPreparedPath(slot, "");
    setMultimodalInputError(slot, message);
    setMultimodalInputPending(slot, false);
    renderMultimodalWorkspace();
    return "";
  }

  setMultimodalInputPending(slot, true);
  setReadonlyStatus(statusElement, `Préparation locale de ${file.name || "ce fichier"}...`);

  try {
    const base64Data = await blobToBase64(file);
    const payload = await tauriInvoke("persist_multimodal_input", {
      slot,
      filename: file.name || `${slot}.bin`,
      data: base64Data,
    });
    const savedPath = String(payload?.savedPath || "").trim();
    setMultimodalPreparedPath(slot, savedPath);
    log(`[info] Fichier multimodal préparé (${slot}) : ${savedPath}`);
    return savedPath;
  } catch (error) {
    const message = error?.message || String(error);
    setMultimodalPreparedPath(slot, "");
    setMultimodalInputError(slot, `Préparation locale impossible : ${message}`);
    log(`[error] Préparation du fichier multimodal (${slot}) impossible : ${message}`);
    return "";
  } finally {
    setMultimodalInputPending(slot, false);
    renderMultimodalWorkspace();
  }
}

async function persistSelectedMultimodalComparisonVideo(side) {
  const normalizedSide = side === "b" ? "b" : "a";
  const input = getMultimodalComparisonVideoInput(normalizedSide);
  const statusElement = getMultimodalComparisonStatusElement(normalizedSide);
  const file = getSelectedFile(input);
  setMultimodalComparisonError(normalizedSide, "");
  resetMultimodalComparisonSourceRuntime(normalizedSide, { rerender: false });

  if (!file) {
    setMultimodalComparisonPreparedVideoPath(normalizedSide, "");
    renderMultimodalWorkspace();
    return "";
  }

  const nativePath = getNativeFilePath(file);
  if (nativePath) {
    setMultimodalComparisonPreparedVideoPath(normalizedSide, nativePath);
    renderMultimodalWorkspace();
    return nativePath;
  }

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    const message = `Impossible de préparer la vidéo ${normalizedSide.toUpperCase()} hors de l'application Tauri.`;
    setMultimodalComparisonPreparedVideoPath(normalizedSide, "");
    setMultimodalComparisonError(normalizedSide, message);
    renderMultimodalWorkspace();
    return "";
  }

  setReadonlyStatus(statusElement, `Préparation locale de la vidéo ${normalizedSide.toUpperCase()}...`);

  try {
    const base64Data = await blobToBase64(file);
    const payload = await tauriInvoke("persist_multimodal_input", {
      slot: "video",
      filename: file.name || `video_${normalizedSide}.bin`,
      data: base64Data,
    });
    const savedPath = String(payload?.savedPath || "").trim();
    setMultimodalComparisonPreparedVideoPath(normalizedSide, savedPath);
    log(`[info] Vidéo comparaison ${normalizedSide.toUpperCase()} préparée : ${savedPath}`);
    return savedPath;
  } catch (error) {
    const message = error?.message || String(error);
    setMultimodalComparisonPreparedVideoPath(normalizedSide, "");
    setMultimodalComparisonError(normalizedSide, `Préparation locale impossible : ${message}`);
    log(`[error] Préparation de la vidéo ${normalizedSide.toUpperCase()} impossible : ${message}`);
    return "";
  } finally {
    renderMultimodalWorkspace();
  }
}

async function persistSelectedMultimodalImages() {
  const files = getSelectedMultimodalImageFiles();
  setMultimodalInputError("images", "");

  if (!files.length) {
    appState.multimodalSelectedImageFiles = [];
    appState.multimodalLocalPaths.imagesDir = "";
    appState.multimodalImagePaths = [];
    if (multimodalImagesFiles) {
      multimodalImagesFiles.value = "";
    }
    renderMultimodalWorkspace();
    return "";
  }

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    setMultimodalInputError("images", "Impossible de préparer les images hors de l'application Tauri.");
    setMultimodalInputPending("images", false);
    renderMultimodalWorkspace();
    return "";
  }

  setMultimodalInputPending("images", true);
  if (multimodalImagesStatus) {
    setReadonlyStatus(multimodalImagesStatus, "Préparation locale des images...");
  }

  try {
    const payloadFiles = [];
    for (const file of files) {
      payloadFiles.push({
        filename: file.name || "image.bin",
        data: await blobToBase64(file)
      });
    }
    const payload = await tauriInvoke("persist_multimodal_image_batch", {
      files: payloadFiles
    });
    appState.multimodalLocalPaths.imagesDir = String(payload?.savedDir || "").trim();
    appState.multimodalImagePaths = Array.isArray(payload?.savedPaths)
      ? payload.savedPaths.map(String).sort((left, right) => naturalCompareValues(left, right))
      : [];
    return appState.multimodalLocalPaths.imagesDir;
  } catch (error) {
    const message = error?.message || String(error);
    setMultimodalInputError("images", `Préparation locale impossible : ${message}`);
    appState.multimodalLocalPaths.imagesDir = "";
    appState.multimodalImagePaths = [];
    return "";
  } finally {
    setMultimodalInputPending("images", false);
    renderMultimodalWorkspace();
  }
}

function getMultimodalFrameRateValue() {
  return multimodalFrameRate25?.checked ? 25 : 1;
}

function getMultimodalIntervalModeValue() {
  return multimodalIntervalMode?.value === "custom" ? "custom" : "full";
}

function getMultimodalStartSec() {
  if (getMultimodalIntervalModeValue() !== "custom") return null;
  return buildSecondsFromHms({
    hours: multimodalExtractStartHours?.value,
    minutes: multimodalExtractStartMinutes?.value,
    seconds: multimodalExtractStartSeconds?.value,
    defaultToZero: true,
  });
}

function getMultimodalEndSec() {
  if (getMultimodalIntervalModeValue() !== "custom") return null;
  return buildSecondsFromHms({
    hours: multimodalExtractEndHours?.value,
    minutes: multimodalExtractEndMinutes?.value,
    seconds: multimodalExtractEndSeconds?.value,
    defaultToZero: false,
  });
}

function getMultimodalFrameQualityValue() {
  return multimodalFrameQualityHigh?.checked ? "high" : "low";
}

function parseNonNegativeInteger(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : fallback;
}

function buildSecondsFromHms({ hours, minutes, seconds, defaultToZero = false } = {}) {
  const rawHours = String(hours ?? "").trim();
  const rawMinutes = String(minutes ?? "").trim();
  const rawSeconds = String(seconds ?? "").trim();
  if (!rawHours && !rawMinutes && !rawSeconds) {
    return defaultToZero ? 0 : null;
  }
  const hh = parseNonNegativeInteger(rawHours || 0, 0);
  const mm = Math.min(59, parseNonNegativeInteger(rawMinutes || 0, 0));
  const ss = Math.min(59, parseNonNegativeInteger(rawSeconds || 0, 0));
  return (hh * 3600) + (mm * 60) + ss;
}

function formatHmsLabel(totalSeconds, { allowOpenEnded = false } = {}) {
  if (totalSeconds === null || totalSeconds === undefined) {
    return allowOpenEnded ? "fin" : "00:00:00";
  }
  const total = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function enforceExclusiveCheckboxPair(primary, secondary) {
  if (!(primary instanceof HTMLInputElement) || !(secondary instanceof HTMLInputElement)) return;
  primary.addEventListener("change", () => {
    if (primary.checked) {
      secondary.checked = false;
    } else if (!secondary.checked) {
      primary.checked = true;
    }
    renderMultimodalWorkspace();
  });
  secondary.addEventListener("change", () => {
    if (secondary.checked) {
      primary.checked = false;
    } else if (!primary.checked) {
      secondary.checked = true;
    }
    renderMultimodalWorkspace();
  });
}

function getMultimodalAudioAmplitudeFilterK() {
  const rawValue = Number(multimodalAudioAmplitudeFilterK?.value ?? 2.0);
  if (!Number.isFinite(rawValue) || rawValue < 0) return 2.0;
  return rawValue;
}

function buildMultimodalFrameExtractionArgs({ withSegments = false } = {}) {
  const source = getPreferredAlignmentSource();
  if (!source?.value) return null;

  const cookiesPath = source.kind === "youtube" ? getMultimodalCookiesPath() : "";
  const startSec = getMultimodalStartSec();
  const endSec = getMultimodalEndSec();
  const args = [
    "--source",
    source.value,
    "--fps",
    String(getMultimodalFrameRateValue()),
    "--quality",
    getMultimodalFrameQualityValue(),
    "--output-dir",
    getMultimodalOutputDir("alignement"),
  ];
  if (cookiesPath) {
    args.push("--cookies", cookiesPath);
  }
  if (startSec !== null) {
    args.push("--start-sec", String(startSec));
  }
  if (endSec !== null) {
    args.push("--end-sec", String(endSec));
  }
  if (withSegments) {
    const segmentsPath = getMultimodalSegmentsPath();
    if (!segmentsPath) return null;
    args.push("--segments-csv", segmentsPath);
    const motionFramesCsvPath = getMultimodalMotionFramesCsvPath();
    if (motionFramesCsvPath) {
      args.push("--motion-frames-csv", motionFramesCsvPath);
    }
    const audioAnomaliesCsvPath = getMultimodalAudioAnomaliesCsvPath();
    const audioPausesCsvPath = getMultimodalAudioPausesCsvPath();
    if (audioAnomaliesCsvPath && isAlignmentAudioOverlayEnabled()) {
      args.push("--audio-anomalies-csv", audioAnomaliesCsvPath);
    }
    if (audioPausesCsvPath && isAlignmentAudioOverlayEnabled()) {
      args.push("--audio-pauses-csv", audioPausesCsvPath);
    }
  }
  return {
    scriptName: "alignement.py",
    args,
    outputDir: getMultimodalOutputDir("alignement"),
  };
}

function buildMultimodalAlignArgs() {
  const request = buildMultimodalFrameExtractionArgs({ withSegments: true });
  if (!request) return null;
  if (multimodalAlignOverlayImages?.checked) request.args.push("--overlay-images");
  if (multimodalAlignOverlaySegments?.checked) request.args.push("--overlay-segments");
  if (multimodalAlignOverlayAudio?.checked) request.args.push("--overlay-audio");
  return request;
}

function buildMultimodalNodesArgs() {
  const alignResult = appState.multimodalResults?.alignement;
  const motionResult = appState.multimodalResults?.mouvements;
  const alignedCsv =
    String(alignResult?.alignmentCsvPath || "").trim() ||
    String(alignResult?.alignedSegmentsCsvPath || "").trim();
  const motionFramesCsv =
    String(motionResult?.framesCsvPath || "").trim();
  if (!alignedCsv || !motionFramesCsv) {
    return null;
  }
  const eventMode = String(multimodalNodesEventMode?.value || "threshold");
  const entropyK = Number(multimodalNodesEntropyK?.value);
  return {
    scriptName: "noeuds.py",
    args: [
      "--aligned-csv",
      alignedCsv,
      "--motion-frames-csv",
      motionFramesCsv,
      "--event-mode",
      eventMode,
      "--entropy-k",
      Number.isFinite(entropyK) ? String(entropyK) : "1.0",
      "--output-dir",
      getMultimodalOutputDir("noeuds"),
    ],
    outputDir: getMultimodalOutputDir("noeuds"),
  };
}

function buildMultimodalAudioArgs() {
  const source = getPreferredAudioSource();
  if (!source?.value) return null;

  const cookiesPath = source.kind === "youtube" ? getMultimodalCookiesPath() : "";
  const startSec = getMultimodalStartSec();
  const endSec = getMultimodalEndSec();
  const args = [
    "--source",
    source.value,
    "--output-dir",
    getMultimodalOutputDir("audio"),
  ];
  if (cookiesPath) {
    args.push("--cookies", cookiesPath);
  }
  if (startSec !== null) {
    args.push("--start-sec", String(startSec));
  }
  if (endSec !== null) {
    args.push("--end-sec", String(endSec));
  }
  args.push("--amplitude-filter-k", String(getMultimodalAudioAmplitudeFilterK()));
  args.push("--word-timestamps");
  return {
    scriptName: "audio.py",
    args,
    outputDir: getMultimodalOutputDir("audio"),
  };
}

function buildMultimodalMotionArgs() {
  const source = getPreferredMotionSource();
  if (!source?.value) return null;

  const cookiesPath = source.kind === "youtube" ? getMultimodalCookiesPath() : "";
  const startSec = getMultimodalStartSec();
  const endSec = getMultimodalEndSec();
  const args = [
    "--source",
    source.value,
    "--output-dir",
    getMultimodalOutputDir("mouvements"),
    "--sample-fps",
    String(getMultimodalFrameRateValue()),
    "--anatomy-backend",
    multimodalMotionAnatomyBackend?.value === "mediapipe" ? "mediapipe" : "opencv",
    "--anatomy-mode",
    multimodalMotionAnatomyMode?.value === "corps_entier" ? "corps_entier" : "visage",
    "--face-analysis-mode",
    multimodalMotionFaceAnalysisMode?.value === "multivisage"
      ? "multivisage"
      : multimodalMotionFaceAnalysisMode?.value === "manuel"
        ? "manuel"
        : "principal",
  ];
  const selectedFaceBox = getMultimodalSelectedFaceBoxArg();
  if (selectedFaceBox) {
    args.push("--selected-face-box", selectedFaceBox);
  }
  const selectedFaceSourceName = getMultimodalSelectedFaceSourceNameArg();
  if (selectedFaceSourceName) {
    args.push("--selected-face-source-name", selectedFaceSourceName);
  }
  const selectedFaceSourceIndex = getMultimodalSelectedFaceSourceIndexArg();
  if (selectedFaceSourceIndex) {
    args.push("--selected-face-source-index", selectedFaceSourceIndex);
  }
  if (cookiesPath) {
    args.push("--cookies", cookiesPath);
  }
  if (startSec !== null) {
    args.push("--start-sec", String(startSec));
  }
  if (endSec !== null) {
    args.push("--end-sec", String(endSec));
  }
  return {
    scriptName: "mouvements.py",
    args,
    outputDir: getMultimodalOutputDir("mouvements"),
  };
}

function buildMultimodalComparisonExtractionRequest(side) {
  const source = getMultimodalComparisonSource(side);
  if (!source?.value) return null;
  const caseDirs = buildMultimodalComparisonCaseDirs(side);
  const comparisonFps = getMultimodalComparisonFrameRateValue();
  const args = [
    "--source",
    source.value,
    "--output-dir",
    caseDirs.extraction,
    "--extract-mp4",
    "--extract-mp3",
    "--extract-frames",
    "--fps",
    String(comparisonFps),
    "--quality",
    getMultimodalFrameQualityValue(),
  ];
  const cookiesPath = source.kind === "youtube" ? getMultimodalCookiesPath() : "";
  const startSec = getMultimodalComparisonStartSec(side);
  const endSec = getMultimodalComparisonEndSec(side);
  if (cookiesPath) {
    args.push("--cookies", cookiesPath);
  }
  if (startSec !== null) {
    args.push("--start-sec", String(startSec));
  }
  if (endSec !== null) {
    args.push("--end-sec", String(endSec));
  }
  return {
    scriptName: "alignement.py",
    args,
    outputDir: caseDirs.extraction,
  };
}

function buildMultimodalComparisonAudioRequest(side, extractionArtifacts) {
  const caseDirs = buildMultimodalComparisonCaseDirs(side);
  const sourceValue =
    extractionArtifacts?.audioMp3Path ||
    extractionArtifacts?.videoPath ||
    getMultimodalComparisonSource(side)?.value ||
    "";
  if (!sourceValue) return null;
  return {
    scriptName: "audio.py",
    args: [
      "--source",
      sourceValue,
      "--output-dir",
      caseDirs.audio,
      "--amplitude-filter-k",
      String(getMultimodalAudioAmplitudeFilterK()),
      "--word-timestamps",
    ],
    outputDir: caseDirs.audio,
  };
}

function buildMultimodalComparisonMotionRequest(side, extractionArtifacts) {
  const caseDirs = buildMultimodalComparisonCaseDirs(side);
  const framesDir = String(extractionArtifacts?.framesDirPath || "").trim();
  if (!framesDir) return null;
  const anatomyMode = multimodalMotionAnatomyMode?.value === "corps_entier" ? "corps_entier" : "visage";
  const requestedFaceAnalysisMode = String(multimodalMotionFaceAnalysisMode?.value || "principal").trim();
  const faceAnalysisMode = requestedFaceAnalysisMode === "multivisage"
    ? "multivisage"
    : requestedFaceAnalysisMode === "manuel"
      ? "manuel"
      : "principal";
  const comparisonFps = getMultimodalComparisonFrameRateValue();
  const args = [
    "--source",
    framesDir,
    "--output-dir",
    caseDirs.mouvements,
    "--sample-fps",
    String(comparisonFps),
    "--anatomy-backend",
    multimodalMotionAnatomyBackend?.value === "mediapipe" ? "mediapipe" : "opencv",
    "--anatomy-mode",
    anatomyMode,
    "--face-analysis-mode",
    faceAnalysisMode,
  ];
  if (faceAnalysisMode === "manuel") {
    const selection = getMultimodalComparisonFaceSelection(side);
    const selectedFaceBox = formatFaceSelectionBoxArg(selection);
    const selectedFaceSourceName = formatFaceSelectionSourceNameArg(selection);
    const selectedFaceSourceIndex = formatFaceSelectionSourceIndexArg(selection);
    if (selectedFaceBox) {
      args.push("--selected-face-box", selectedFaceBox);
    }
    if (selectedFaceSourceName) {
      args.push("--selected-face-source-name", selectedFaceSourceName);
    }
    if (selectedFaceSourceIndex) {
      args.push("--selected-face-source-index", selectedFaceSourceIndex);
    }
  }
  return {
    scriptName: "mouvements.py",
    args,
    outputDir: caseDirs.mouvements,
  };
}

function buildMultimodalComparisonAlignRequest(side, extractionArtifacts, audioArtifacts, motionArtifacts) {
  const caseDirs = buildMultimodalComparisonCaseDirs(side);
  const framesDir = String(extractionArtifacts?.framesDirPath || "").trim();
  const segmentsCsvPath = String(audioArtifacts?.segmentsGlobalCsvPath || "").trim();
  if (!framesDir || !segmentsCsvPath) return null;
  const comparisonFps = getMultimodalComparisonFrameRateValue();
  const args = [
    "--source",
    framesDir,
    "--output-dir",
    caseDirs.alignement,
    "--fps",
    String(comparisonFps),
    "--quality",
    getMultimodalFrameQualityValue(),
    "--segments-csv",
    segmentsCsvPath,
  ];
  if (motionArtifacts?.framesCsvPath) {
    args.push("--motion-frames-csv", motionArtifacts.framesCsvPath);
  }
  if (audioArtifacts?.anomaliesCsvPath) {
    args.push("--audio-anomalies-csv", audioArtifacts.anomaliesCsvPath);
  }
  if (audioArtifacts?.pausesCsvPath) {
    args.push("--audio-pauses-csv", audioArtifacts.pausesCsvPath);
  }
  return {
    scriptName: "alignement.py",
    args,
    outputDir: caseDirs.alignement,
  };
}

function buildMultimodalComparisonAbRequest(caseA, caseB) {
  const outputDir = getMultimodalComparisonOutputDir();
  const alignedCsvA = String(caseA?.align?.alignedSegmentsCsvPath || "").trim();
  const alignedCsvB = String(caseB?.align?.alignedSegmentsCsvPath || "").trim();
  if (!alignedCsvA || !alignedCsvB) return null;
  const args = [
    "--aligned-csv-a",
    alignedCsvA,
    "--aligned-csv-b",
    alignedCsvB,
    "--label-a",
    String(caseA?.label || "Vidéo A"),
    "--label-b",
    String(caseB?.label || "Vidéo B"),
  ];
  const pausesCsvA = String(caseA?.audio?.pausesCsvPath || "").trim();
  const pausesCsvB = String(caseB?.audio?.pausesCsvPath || "").trim();
  if (pausesCsvA) {
    args.push("--audio-pauses-csv-a", pausesCsvA);
  }
  if (pausesCsvB) {
    args.push("--audio-pauses-csv-b", pausesCsvB);
  }
  args.push("--output-dir", outputDir);
  return {
    scriptName: "comparaison_ab.py",
    args,
    outputDir,
  };
}

function getParsedMotionSummary() {
  const artifact = appState.multimodalResults?.mouvements?.summaryJsonArtifact;
  if (!artifact) return null;
  try {
    return JSON.parse(artifactDataToText(artifact));
  } catch (_error) {
    return null;
  }
}

function updateMotionRunStatusFromSummary() {
  const summary = getParsedMotionSummary();
  if (!summary) return;

  const requestedBackend = String(summary.anatomy_backend_requested || "").trim();
  const effectiveBackend = String(summary.anatomy_backend_effective || "").trim();
  const faceAnalysisMode = String(summary.face_analysis_mode || "").trim();
  const manualIdentityBackend = String(summary.manual_identity_backend || "").trim();
  const manualIdentityWarning = String(summary.manual_identity_warning || "").trim();
  const multifaceRows = Number(summary.multiface_rows);
  const warning = String(summary.anatomy_backend_warning || "").trim();
  const motionRows = getParsedMotionRows() || [];
  const parts = [];

  if (requestedBackend && effectiveBackend) {
    if (requestedBackend === effectiveBackend) {
      parts.push(`backend ${effectiveBackend} utilisé`);
    } else {
      parts.push(`backend demandé ${requestedBackend}, fallback ${effectiveBackend}`);
    }
  }
  if (faceAnalysisMode) {
    parts.push(
      faceAnalysisMode === "multivisage"
        ? "mode multivisage"
        : faceAnalysisMode === "manuel"
          ? "mode sélection souris"
          : "mode visage principal"
    );
  }
  if (faceAnalysisMode === "manuel" && manualIdentityBackend) {
    parts.push(`ré-identification ${manualIdentityBackend}`);
  }
  if (faceAnalysisMode === "manuel" && motionRows.length) {
    const trackedRows = motionRows.filter((row) => {
      const status = String(row?.tracked_face_status || "").trim().toLowerCase();
      return Boolean(status) && status !== "attente image de référence";
    });
    const lockedRows = trackedRows.filter((row) => String(row?.tracked_face_locked || "").trim().toLowerCase() === "oui");
    const lostRows = trackedRows.filter((row) => String(row?.tracked_face_lost || "").trim().toLowerCase() === "oui");
    const confidenceValues = trackedRows
      .map((row) => Number(row?.tracked_face_confidence))
      .filter((value) => Number.isFinite(value) && value > 0);
    const identityValues = trackedRows
      .map((row) => Number(row?.tracked_face_identity_similarity))
      .filter((value) => Number.isFinite(value) && value > 0);
    if (trackedRows.length) {
      parts.push(`${lockedRows.length}/${trackedRows.length} transitions verrouillées`);
    }
    if (confidenceValues.length) {
      const confidenceMean = confidenceValues.reduce((sum, value) => sum + value, 0) / confidenceValues.length;
      parts.push(`confiance moyenne ${(confidenceMean * 100).toFixed(0)}%`);
    }
    if (identityValues.length) {
      const identityMean = identityValues.reduce((sum, value) => sum + value, 0) / identityValues.length;
      parts.push(`similarité identité moyenne ${(identityMean * 100).toFixed(0)}%`);
    }
    if (lostRows.length) {
      parts.push(`${lostRows.length} transition(s) perdues`);
    }
  }
  if (Number.isFinite(multifaceRows) && multifaceRows > 0) {
    parts.push(`${multifaceRows} lignes exportées dans mouvements_multivisage.csv`);
  }
  if (warning) {
    parts.push(warning);
  }
  if (faceAnalysisMode === "manuel" && manualIdentityWarning) {
    parts.push(manualIdentityWarning);
  }

  if (parts.length) {
    setReadonlyStatus(multimodalMotionRunStatus, parts.join(" · "), {
      isError: requestedBackend === "mediapipe" && effectiveBackend !== "mediapipe",
    });
  }
}

function renderMultimodalJsonBlock(container, jsonText, emptyMessage) {
  clearContainer(container);

  if (!jsonText) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const pre = document.createElement("pre");
  pre.className = "readonly-field";
  try {
    pre.textContent = JSON.stringify(JSON.parse(jsonText), null, 2);
  } catch (_error) {
    pre.textContent = jsonText;
  }
  container.appendChild(pre);
}

function renderMultimodalAudioResults() {
  const audioResult = appState.multimodalResults?.audio;

  clearContainer(multimodalAudioPausesPlot);
  if (audioResult?.pausesPngArtifact) {
    const image = document.createElement("img");
    image.className = "result-image";
    image.alt = "Pauses avant segment";
    image.src = artifactDataToObjectUrl(audioResult.pausesPngArtifact);
    multimodalAudioPausesPlot.appendChild(image);
  } else {
    multimodalAudioPausesPlot.appendChild(createEmptyState("Aucun graphe des pauses n'est disponible."));
  }

  clearContainer(multimodalAudioSpeechRatePlot);
  if (audioResult?.speechRatePngArtifact) {
    const image = document.createElement("img");
    image.className = "result-image";
    image.alt = "Débit de parole";
    image.src = artifactDataToObjectUrl(audioResult.speechRatePngArtifact);
    multimodalAudioSpeechRatePlot.appendChild(image);
  } else {
    multimodalAudioSpeechRatePlot.appendChild(createEmptyState("Aucun graphe du débit de parole n'est disponible."));
  }

  clearContainer(multimodalAudioAnomaliesPlot);
  if (audioResult?.anomaliesPngArtifact) {
    const image = document.createElement("img");
    image.className = "result-image";
    image.alt = "Anomalies audio";
    image.src = artifactDataToObjectUrl(audioResult.anomaliesPngArtifact);
    multimodalAudioAnomaliesPlot.appendChild(image);
  } else {
    multimodalAudioAnomaliesPlot.appendChild(createEmptyState("Aucun graphe d'anomalies audio n'est disponible."));
  }

  renderTable(
    multimodalAudioAnomaliesConcordancier,
    audioResult?.anomaliesConcordancierCsvArtifact ? parseCsv(artifactDataToText(audioResult.anomaliesConcordancierCsvArtifact)) : null,
    {
      title: "Concordancier des segments synchronisés sur les anomalies",
      maxRows: 40,
      emptyMessage: "Aucun concordancier d'anomalies n'est disponible."
    }
  );

  renderTable(
    multimodalAudioTable,
    audioResult?.segmentsCsvArtifact ? parseCsv(artifactDataToText(audioResult.segmentsCsvArtifact)) : null,
    {
      title: "Segments transcrits et débit de parole",
      maxRows: 40,
      emptyMessage: "Aucun segment transcrit n'est disponible."
    }
  );
}

function getParsedMultimodalComparisonAbSummary() {
  const artifact = appState.multimodalComparisonAB?.result?.summaryJsonArtifact;
  if (!artifact) return null;
  try {
    const parsed = JSON.parse(artifactDataToText(artifact));
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (_error) {
    return null;
  }
}

function getParsedMultimodalComparisonAbTimeline() {
  const artifact = appState.multimodalComparisonAB?.result?.timelineCsvArtifact;
  if (!artifact) return null;
  return parseCsv(artifactDataToText(artifact));
}

function getParsedMultimodalComparisonAbTimelineRows() {
  const parsed = getParsedMultimodalComparisonAbTimeline();
  return parsed ? rowsFromParsedCsv(parsed) : [];
}

function getParsedMultimodalComparisonAbIndicators() {
  const artifact = appState.multimodalComparisonAB?.result?.indicatorsCsvArtifact;
  if (!artifact) return null;
  return parseCsv(artifactDataToText(artifact));
}

function remapParsedHeaders(parsed, headerMap = {}) {
  if (!parsed?.headers?.length || !Array.isArray(parsed.rows)) {
    return parsed;
  }
  return {
    headers: parsed.headers.map((header) => headerMap[header] || header),
    rows: parsed.rows,
  };
}

function selectAndRemapParsedHeaders(parsed, allowedHeaders = [], headerMap = {}) {
  if (!parsed?.headers?.length || !Array.isArray(parsed.rows)) {
    return parsed;
  }
  const selectedIndexes = parsed.headers
    .map((header, index) => ({ header, index }))
    .filter(({ header }) => !allowedHeaders.length || allowedHeaders.includes(header));
  return {
    headers: selectedIndexes.map(({ header }) => headerMap[header] || header),
    rows: parsed.rows.map((row) => selectedIndexes.map(({ index }) => row[index] ?? "")),
  };
}

function getMultimodalComparisonCase(side) {
  const result = appState.multimodalComparisonAB?.result;
  if (!result) return null;
  return side === "b" ? result.caseB || null : result.caseA || null;
}

function getParsedMultimodalComparisonCaseMotionRows(side) {
  const caseData = getMultimodalComparisonCase(side);
  const framesCsvPath = String(caseData?.motion?.framesCsvPath || "").trim();
  if (!framesCsvPath) return [];
  const artifact = findArtifactForAbsolutePath(
    caseData?.motion?.artifacts || [],
    caseData?.motion?.outputDir || "",
    framesCsvPath
  );
  if (!artifact) return [];
  return rowsFromParsedCsv(parseCsv(artifactDataToText(artifact)));
}

function getParsedMultimodalComparisonCaseAlignmentRows(side) {
  const caseData = getMultimodalComparisonCase(side);
  const alignmentArtifact = caseData?.align?.alignmentCsvArtifact
    || findArtifactForAbsolutePath(
      caseData?.align?.artifacts || [],
      caseData?.align?.outputDir || "",
      caseData?.align?.alignmentCsvPath || ""
    );
  if (!alignmentArtifact) return [];
  return rowsFromParsedCsv(parseCsv(artifactDataToText(alignmentArtifact)));
}

function getParsedMultimodalComparisonCaseAudioAnomalyRows(side) {
  const caseData = getMultimodalComparisonCase(side);
  const anomalyArtifact = findArtifactForAbsolutePath(
    caseData?.audio?.artifacts || [],
    caseData?.audio?.outputDir || "",
    caseData?.audio?.anomaliesCsvPath || ""
  );
  if (!anomalyArtifact) return [];
  return rowsFromParsedCsv(parseCsv(artifactDataToText(anomalyArtifact)));
}

function getParsedMultimodalComparisonCasePauseRows(side) {
  const caseData = getMultimodalComparisonCase(side);
  const pauseArtifact = findArtifactForAbsolutePath(
    caseData?.audio?.artifacts || [],
    caseData?.audio?.outputDir || "",
    caseData?.audio?.pausesCsvPath || ""
  );
  if (!pauseArtifact) return [];
  return rowsFromParsedCsv(parseCsv(artifactDataToText(pauseArtifact)));
}

function getParsedMultimodalComparisonCaseTimelineData(side) {
  return buildAlignmentTimelineDataFromRows(
    getParsedMultimodalComparisonCaseAlignmentRows(side),
    getParsedMultimodalComparisonCaseMotionRows(side),
    getParsedMultimodalComparisonCaseAudioAnomalyRows(side),
    getParsedMultimodalComparisonCasePauseRows(side),
  );
}

function findMultimodalComparisonCaseMotionRow(side, frameId, timeSec) {
  const rows = getParsedMultimodalComparisonCaseMotionRows(side);
  if (!rows.length) return null;
  if (Number.isFinite(frameId)) {
    const byFrame = rows.find((row) => Number(row?.frame_index) === frameId);
    if (byFrame) return byFrame;
  }
  if (!Number.isFinite(timeSec)) return null;
  return getClosestMotionRowByTime(rows, timeSec);
}

function resolveMultimodalComparisonCaseImageSource(side, motionRow, requestedView) {
  const caseData = getMultimodalComparisonCase(side);
  const config = getAlignmentImageViewConfig(requestedView);
  const fallbackPath = String(motionRow?.frame_preview_path || motionRow?.image_path || "").trim();
  const requestedPath = String(motionRow?.[config.motionPathKey] || "").trim();
  const absolutePath = requestedPath || fallbackPath;
  const effectiveLabel = requestedPath ? config.label : "Image brute";
  const artifact = absolutePath
    ? findArtifactForAbsolutePath(caseData?.motion?.artifacts || [], caseData?.motion?.outputDir || "", absolutePath)
    : null;
  const src = artifact ? artifactDataToObjectUrl(artifact) : maybeCreateLocalFileUrl(absolutePath);
  return {
    src,
    label: effectiveLabel,
    absolutePath,
  };
}

function resolveMultimodalComparisonCaseImageSourceForMotionRow(side, motionRow, requestedView) {
  return resolveMultimodalComparisonCaseImageSource(side, motionRow, requestedView);
}

function formatComparisonNumber(value, digits = 3) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(digits) : "—";
}

function buildMultimodalComparisonAbMomentRows(rows) {
  const moments = [];
  let previousKey = "";
  rows.forEach((row) => {
    const key = [
      String(row.segment_a_id || "").trim(),
      String(row.segment_b_id || "").trim(),
      String(row.nearest_frame_a_id || "").trim(),
      String(row.nearest_frame_b_id || "").trim(),
      String(row.anomalie_audio_a || "").trim(),
      String(row.anomalie_audio_b || "").trim(),
    ].join("|");
    if (!key || key === previousKey) return;
    previousKey = key;
    moments.push(row);
  });
  return moments;
}

function renderMultimodalComparisonAbSummaryResult(container, summary) {
  clearContainer(container);
  if (!summary) {
    container.appendChild(createEmptyState("Aucun résumé de comparaison A/B n'est disponible."));
    return;
  }

  const block = document.createElement("div");
  block.className = "section-stack";

  const meta = document.createElement("div");
  meta.className = "readonly-field";
  meta.textContent = [
    `${summary?.labels?.a || "A"} · durée : ${Number(summary?.durations_sec?.a || 0).toFixed(2)} s · segments : ${summary?.counts?.segments_a ?? 0}`,
    `${summary?.labels?.b || "B"} · durée : ${Number(summary?.durations_sec?.b || 0).toFixed(2)} s · segments : ${summary?.counts?.segments_b ?? 0}`,
    `Écart mouvement moyen (B - A) : ${summary?.key_differences?.motion_mean_delta ?? ""}`,
    `Écart entropie directionnelle (B - A) : ${summary?.key_differences?.directional_entropy_delta ?? ""}`,
    `Écart débit de parole (B - A) : ${summary?.key_differences?.speech_rate_delta ?? ""}`,
    `Écart ratio anomalies audio (B - A) : ${summary?.key_differences?.audio_anomaly_rate_delta ?? ""}`,
  ].join("\n");
  block.appendChild(meta);
  container.appendChild(block);
}

function createMultimodalComparisonAbColumn(side, row, requestedView) {
  const label = side === "b" ? "Vidéo B" : "Vidéo A";
  const suffix = side === "b" ? "b" : "a";
  const section = document.createElement("section");
  section.className = "comparison-ab-column";

  const title = document.createElement("h5");
  title.textContent = label;
  section.appendChild(title);

  const frameId = Number(row[`nearest_frame_${suffix}_id`]);
  const timeSec = Number(row[`time_${suffix}_sec`]);
  const motionRow = findMultimodalComparisonCaseMotionRow(suffix, frameId, timeSec);
  if (motionRow) {
    const resolvedImage = resolveMultimodalComparisonCaseImageSource(suffix, motionRow, requestedView);
    if (resolvedImage.src) {
      section.appendChild(
        createPreviewableImage({
          src: resolvedImage.src,
          alt: `${label} · image synchronisée`,
          title: `${label} · image synchronisée`,
          kicker: `Comparaison A/B · ${resolvedImage.label}`,
        })
      );
      const caption = document.createElement("p");
      caption.className = "result-gallery-caption";
      caption.textContent = [
        Number.isFinite(frameId) ? `image ${frameId}` : "",
        Number.isFinite(timeSec) ? `${timeSec.toFixed(2)} s` : "",
        resolvedImage.label,
      ].filter(Boolean).join(" · ");
      section.appendChild(caption);
    }
  }

  const textBlock = document.createElement("p");
  textBlock.className = "comparison-ab-text";
  textBlock.textContent = String(row[`text_${suffix}`] || "").trim() || "Aucun segment actif à ce moment.";
  section.appendChild(textBlock);

  const meta = document.createElement("div");
  meta.className = "readonly-field";
  meta.textContent = [
    `Segment : ${String(row[`segment_${suffix}_id`] || "").trim() || "—"}`,
    `Temps : ${Number.isFinite(timeSec) ? `${timeSec.toFixed(2)} s` : "—"}`,
    `Débit de parole : ${formatComparisonNumber(row[`words_per_sec_${suffix}`], 2)}`,
    `Anomalie audio : ${String(row[`anomalie_audio_${suffix}`] || "").trim() || "non"}`,
    `Mouvement moyen : ${formatComparisonNumber(row[`motion_mean_${suffix}`])}`,
    `Entropie directionnelle : ${formatComparisonNumber(row[`entropy_${suffix}`])}`,
    `Direction : ${String(row[`direction_${suffix}`] || "").trim() || "—"}`,
  ].join("\n");
  section.appendChild(meta);

  return section;
}

function renderMultimodalComparisonAbAlignedView(container) {
  clearContainer(container);
  const summary = getParsedMultimodalComparisonAbSummary();
  const timelineA = getParsedMultimodalComparisonCaseTimelineData("a");
  const timelineB = getParsedMultimodalComparisonCaseTimelineData("b");
  const motionRowsA = getParsedMultimodalComparisonCaseMotionRows("a");
  const motionRowsB = getParsedMultimodalComparisonCaseMotionRows("b");
  const hasA = timelineA?.tracks && Object.values(timelineA.tracks).some((items) => Array.isArray(items) && items.length);
  const hasB = timelineB?.tracks && Object.values(timelineB.tracks).some((items) => Array.isArray(items) && items.length);

  if (!hasA && !hasB) {
    container.appendChild(createEmptyState("Aucune timeline d'alignement A/B n'est disponible."));
    return;
  }

  const sections = [
    {
      side: "a",
      heading: "Vidéo A",
      sourceLabel: String(summary?.labels?.a || "Vidéo A"),
      timeline: timelineA,
      motionRows: motionRowsA,
      emptyMessage: "Aucune timeline d'alignement n'est disponible pour la vidéo A.",
    },
    {
      side: "b",
      heading: "Vidéo B",
      sourceLabel: String(summary?.labels?.b || "Vidéo B"),
      timeline: timelineB,
      motionRows: motionRowsB,
      emptyMessage: "Aucune timeline d'alignement n'est disponible pour la vidéo B.",
    },
  ];

  const tables = document.createElement("div");
  tables.className = "comparison-ab-timeline-tables";

  sections.forEach((sectionConfig) => {
    const section = document.createElement("section");
    section.className = "card section-card comparison-ab-timeline-card";

    const header = document.createElement("div");
    header.className = "comparison-ab-timeline-header";

    const titleWrap = document.createElement("div");
    const title = document.createElement("h4");
    title.className = "comparison-ab-timeline-title";
    title.textContent = sectionConfig.heading;
    titleWrap.appendChild(title);

    const subtitle = document.createElement("p");
    subtitle.className = "comparison-ab-timeline-source";
    subtitle.textContent = sectionConfig.sourceLabel;
    titleWrap.appendChild(subtitle);

    header.appendChild(titleWrap);
    section.appendChild(header);

    const timelineContainer = document.createElement("div");
    timelineContainer.className = "comparison-ab-timeline-table";
    section.appendChild(timelineContainer);
    renderAlignmentTimelineLike(timelineContainer, {
      timeline: sectionConfig.timeline,
      motionRows: sectionConfig.motionRows,
      requestedView: getSelectedAlignmentImageView(),
      imageTrackViews: ["brute", "magnitude", "entropie", "hsv", "vecteurs", "superposition", "anatomie"],
      showAudioTrack: true,
      showPauseTrack: true,
      resolveMotionImageSource: (motionRow, view) =>
        resolveMultimodalComparisonCaseImageSourceForMotionRow(sectionConfig.side, motionRow, view),
      emptyMessage: sectionConfig.emptyMessage,
      kickerPrefix: "Comparaison A/B",
      summaryText: `Timeline multimodale · ${sectionConfig.heading}`,
      showAudioTrack: true,
      showPauseTrack: true,
      timelineScaleOverride: 180,
      curveModeOverride: "raw",
    });

    tables.appendChild(section);
  });

  container.appendChild(tables);
}

function createMultimodalComparisonAbSettingsBlock(title, lines = []) {
  const block = document.createElement("section");
  block.className = "comparison-ab-settings-block";

  const heading = document.createElement("h5");
  heading.textContent = title;
  block.appendChild(heading);

  lines
    .map((line) => String(line || "").trim())
    .filter(Boolean)
    .forEach((line) => {
      const field = document.createElement("p");
      field.className = "readonly-field";
      field.textContent = line;
      block.appendChild(field);
    });

  return block;
}

function getMultimodalComparisonFaceAnalysisLabel() {
  const anatomyMode = multimodalMotionAnatomyMode?.value === "corps_entier" ? "corps_entier" : "visage";
  if (anatomyMode === "corps_entier") {
    return "corps entier";
  }
  const rawValue = String(multimodalMotionFaceAnalysisMode?.value || "principal").trim();
  if (rawValue === "multivisage") return "multivisage";
  if (rawValue === "manual") return "sélection à la souris";
  return "visage principal";
}

function renderMultimodalComparisonAbSettings() {
  if (!multimodalCompareAbSettingsContent) return;
  clearContainer(multimodalCompareAbSettingsContent);

  const sections = document.createElement("div");
  sections.className = "comparison-ab-settings-sections";

  const comparisonFps = getMultimodalComparisonFrameRateValue();
  const qualityLabel = getMultimodalFrameQualityValue() === "high"
    ? "très haute définition (1920 px)"
    : "définition standard (1024 px)";
  const anatomyBackendLabel = multimodalMotionAnatomyBackend?.value === "mediapipe" ? "MediaPipe" : "OpenCV";
  const anatomyModeLabel = multimodalMotionAnatomyMode?.value === "corps_entier" ? "corps entier" : "visage";
  const startA = getMultimodalComparisonStartSec("a");
  const endA = getMultimodalComparisonEndSec("a");
  const startB = getMultimodalComparisonStartSec("b");
  const endB = getMultimodalComparisonEndSec("b");
  const sourceA = getMultimodalComparisonLabel("a");
  const sourceB = getMultimodalComparisonLabel("b");

  sections.appendChild(createMultimodalComparisonAbSettingsBlock("Extraction et comparaison", [
    `Vidéo A : ${sourceA} · ${startA === null && endA === null ? "toute la vidéo" : `${formatHmsLabel(startA)} → ${formatHmsLabel(endA, { allowOpenEnded: true })}`}`,
    `Vidéo B : ${sourceB} · ${startB === null && endB === null ? "toute la vidéo" : `${formatHmsLabel(startB)} → ${formatHmsLabel(endB, { allowOpenEnded: true })}`}`,
    `Cadence A/B : ${comparisonFps} image${comparisonFps > 1 ? "s" : ""}/seconde`,
    `Dossier de sortie : ${getMultimodalComparisonOutputDir()}`,
  ]));

  sections.appendChild(createMultimodalComparisonAbSettingsBlock("Audio", [
    `Anomalies audio : moyenne ± ${getMultimodalAudioAmplitudeFilterK()} écart-type`,
    "Fenêtre audio : 1 seconde",
    "Pistes audio rendues : anomalies audio et pauses",
  ]));

  sections.appendChild(createMultimodalComparisonAbSettingsBlock("Images et mouvements", [
    `Qualité d'image : ${qualityLabel}`,
    "Rendus affichés : image brute, magnitude, entropie directionnelle, HSV, vecteurs, superposition, annotée",
    `Backend anatomique : ${anatomyBackendLabel}`,
    `Zone d'analyse : ${anatomyModeLabel}`,
    `Analyse visage : ${getMultimodalComparisonFaceAnalysisLabel()}`,
  ]));

  sections.appendChild(createMultimodalComparisonAbSettingsBlock("Lecture de la timeline", [
    `Zoom timeline : ${getSelectedAlignmentTimelineScale()} px/seconde`,
    "Courbes indicateurs : brut",
    "Pistes affichées : images, texte, pauses, audio, mouvement moyen, entropie directionnelle",
  ]));

  multimodalCompareAbSettingsContent.appendChild(sections);
}

function renderMultimodalComparisonAbResults() {
  const result = appState.multimodalComparisonAB?.result;
  const summary = getParsedMultimodalComparisonAbSummary();

  if (multimodalCompareAbSettingsPanel) {
    multimodalCompareAbSettingsPanel.hidden = true;
  }
  if (multimodalCompareAbToggleSettingsBtn) {
    multimodalCompareAbToggleSettingsBtn.textContent = "Paramètres";
    multimodalCompareAbToggleSettingsBtn.setAttribute("aria-pressed", "false");
  }
  if (multimodalCompareAbResultsCard) {
    multimodalCompareAbResultsCard.classList.toggle("is-fullscreen", isMultimodalComparisonAbFullscreen());
  }
  if (document?.body) {
    document.body.classList.toggle("comparison-ab-fullscreen-open", isMultimodalComparisonAbFullscreen());
  }
  renderMultimodalComparisonAbSummaryResult(
    multimodalCompareAbSummary,
    summary
  );
  renderMultimodalComparisonAbAlignedView(multimodalCompareAbAlignedView);

  const labelA = String(summary?.labels?.a || "Vidéo A").trim() || "Vidéo A";
  const labelB = String(summary?.labels?.b || "Vidéo B").trim() || "Vidéo B";
  const timelineHeaderMap = {
    time_a_sec: `Repère début ${labelA} (s)`,
    time_a_end_sec: `Temps fin ${labelA} (s)`,
    segment_a_id: `Segment ${labelA}`,
    text_a: `Texte ${labelA}`,
    motion_mean_a: `Mouvement moyen ${labelA}`,
    entropy_a: `Entropie directionnelle ${labelA}`,
    motion_energy_a: `Énergie de mouvement ${labelA}`,
    words_per_sec_a: `Débit de parole ${labelA}`,
    anomalie_audio_a: `Anomalie audio ${labelA}`,
    direction_a: `Direction ${labelA}`,
    nearest_frame_a_id: `Image ${labelA}`,
    time_b_sec: `Repère début ${labelB} (s)`,
    time_b_end_sec: `Temps fin ${labelB} (s)`,
    segment_b_id: `Segment ${labelB}`,
    text_b: `Texte ${labelB}`,
    motion_mean_b: `Mouvement moyen ${labelB}`,
    entropy_b: `Entropie directionnelle ${labelB}`,
    motion_energy_b: `Énergie de mouvement ${labelB}`,
    words_per_sec_b: `Débit de parole ${labelB}`,
    anomalie_audio_b: `Anomalie audio ${labelB}`,
    direction_b: `Direction ${labelB}`,
    nearest_frame_b_id: `Image ${labelB}`,
  };
  const timelineVisibleHeaders = [
    "time_a_sec",
    "time_a_end_sec",
    "segment_a_id",
    "text_a",
    "motion_mean_a",
    "entropy_a",
    "motion_energy_a",
    "words_per_sec_a",
    "anomalie_audio_a",
    "direction_a",
    "nearest_frame_a_id",
    "time_b_sec",
    "time_b_end_sec",
    "segment_b_id",
    "text_b",
    "motion_mean_b",
    "entropy_b",
    "motion_energy_b",
    "words_per_sec_b",
    "anomalie_audio_b",
    "direction_b",
    "nearest_frame_b_id",
  ];

  const indicatorsHeaderMap = {
    indicator: "Indicateur",
    unite: "Unité",
    [`${labelA}_mean`]: `${labelA} · moyenne`,
    [`${labelA}_std`]: `${labelA} · écart-type`,
    [`${labelA}_min`]: `${labelA} · min`,
    [`${labelA}_max`]: `${labelA} · max`,
    [`${labelB}_mean`]: `${labelB} · moyenne`,
    [`${labelB}_std`]: `${labelB} · écart-type`,
    [`${labelB}_min`]: `${labelB} · min`,
    [`${labelB}_max`]: `${labelB} · max`,
    delta_b_minus_a: `Écart ${labelB} - ${labelA}`,
  };

  renderTable(
    multimodalCompareAbTimelineTable,
    result?.timelineCsvArtifact
      ? selectAndRemapParsedHeaders(getParsedMultimodalComparisonAbTimeline(), timelineVisibleHeaders, timelineHeaderMap)
      : null,
    {
      title: "Timeline A/B",
      maxRows: 101,
      emptyMessage: "Aucune timeline A/B n'est disponible.",
    }
  );

  renderTable(
    multimodalCompareAbIndicatorsTable,
    result?.indicatorsCsvArtifact
      ? remapParsedHeaders(getParsedMultimodalComparisonAbIndicators(), indicatorsHeaderMap)
      : null,
    {
      title: "Indicateurs comparés",
      maxRows: 40,
      emptyMessage: "Aucun tableau d'indicateurs comparés n'est disponible.",
    }
  );
}

function getParsedSegmentsSourceRows() {
  const selectedFile = getSelectedMultimodalSegmentsFile();
  if (
    selectedFile &&
    appState.multimodalSegmentsPreviewParsed?.headers?.length &&
    isValidAlignmentSegmentsParsed(appState.multimodalSegmentsPreviewParsed)
  ) {
    return parsedToRowObjects(appState.multimodalSegmentsPreviewParsed);
  }

  const audioSegmentsArtifact =
    appState.multimodalResults?.audio?.segmentsGlobalCsvArtifact
    || appState.multimodalResults?.audio?.segmentsCsvArtifact;
  if (audioSegmentsArtifact) {
    return parsedToRowObjects(parseCsv(artifactDataToText(audioSegmentsArtifact)));
  }

  if (appState.multimodalSegmentsPreviewParsed?.headers?.length) {
    return parsedToRowObjects(appState.multimodalSegmentsPreviewParsed);
  }

  return [];
}

function getParsedAudioAnomalyRows() {
  if (!isAlignmentAudioOverlayEnabled()) return [];
  const artifact = appState.multimodalResults?.audio?.anomaliesCsvArtifact;
  if (!artifact) return [];
  return parsedToRowObjects(parseCsv(artifactDataToText(artifact)));
}

function getParsedAudioPauseRows() {
  if (!isAlignmentAudioOverlayEnabled()) return [];
  const artifact = appState.multimodalResults?.audio?.pausesCsvArtifact;
  if (!artifact) return [];
  return parsedToRowObjects(parseCsv(artifactDataToText(artifact)));
}

function getClosestMotionRowByTime(rows, timeSec) {
  if (!Array.isArray(rows) || !rows.length || !Number.isFinite(timeSec)) return null;
  let bestRow = null;
  let bestDelta = Number.POSITIVE_INFINITY;
  rows.forEach((row) => {
    const rowTime = Number(row?.time_sec);
    if (!Number.isFinite(rowTime)) return;
    const delta = Math.abs(rowTime - timeSec);
    if (delta < bestDelta) {
      bestDelta = delta;
      bestRow = row;
    }
  });
  return bestRow;
}

function getMotionRowsWithinAlignmentSegment(row, motionRows) {
  if (!Array.isArray(motionRows) || !motionRows.length) return [];
  const startSec = Number(row?.start_sec);
  const endSec = Number(row?.end_sec);
  if (!Number.isFinite(startSec) || !Number.isFinite(endSec)) return [];
  const rows = motionRows.filter((motionRow) => {
    const rowTime = Number(motionRow?.time_sec);
    return Number.isFinite(rowTime) && rowTime >= startSec && rowTime <= endSec;
  });
  const seen = new Set();
  return rows
    .sort((left, right) => Number(left?.time_sec || 0) - Number(right?.time_sec || 0))
    .filter((motionRow) => {
      const frameIndex = String(motionRow?.frame_index || "").trim();
      const imagePath = normalizePath(String(motionRow?.image_path || motionRow?.frame_preview_path || "").trim());
      const key = frameIndex || imagePath;
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function parseAlignmentWordTimestamps(rawValue) {
  const source = Array.isArray(rawValue)
    ? rawValue
    : (() => {
      const text = String(rawValue || "").trim();
      if (!text) return [];
      try {
        return JSON.parse(text);
      } catch (_error) {
        return [];
      }
    })();

  if (!Array.isArray(source)) return [];
  return source
    .map((item) => {
      const startSec = Number(item?.start_sec ?? item?.start);
      const endSec = Number(item?.end_sec ?? item?.end);
      const word = String(item?.word || item?.text || "").trim();
      if (!Number.isFinite(startSec) || !Number.isFinite(endSec) || !word) {
        return null;
      }
      return {
        start_sec: startSec,
        end_sec: Math.max(startSec, endSec),
        word,
      };
    })
    .filter(Boolean)
    .sort((left, right) => Number(left.start_sec) - Number(right.start_sec));
}

function buildApproxAlignmentWordItems(text, startSec, endSec) {
  const value = String(text || "").trim();
  const matches = Array.from(value.matchAll(/[A-Za-zÀ-ÿ0-9'’-]+/g));
  if (!matches.length || !Number.isFinite(startSec) || !Number.isFinite(endSec) || endSec <= startSec) {
    return [];
  }
  const durationSec = endSec - startSec;
  return matches.map((match, index) => {
    const wordStartSec = startSec + ((index / matches.length) * durationSec);
    const wordEndSec = startSec + (((index + 1) / matches.length) * durationSec);
    return {
      start_sec: wordStartSec,
      end_sec: Math.max(wordStartSec, wordEndSec),
      word: String(match?.[0] || "").trim(),
    };
  });
}

function getAlignmentWordItems(row) {
  const parsedItems = parseAlignmentWordTimestamps(row?.word_items || row?.word_timestamps_json);
  if (parsedItems.length) {
    return parsedItems;
  }
  const startSec = Number(row?.start_sec);
  const endSec = Number(row?.end_sec);
  return buildApproxAlignmentWordItems(String(row?.text || ""), startSec, endSec);
}

function buildDerivedAlignmentRows() {
  const segmentRows = getParsedSegmentsSourceRows();
  const motionRows = getParsedMotionRows();
  if (!segmentRows.length || !motionRows?.length) {
    return [];
  }

  const anomalyRows = getParsedAudioAnomalyRows()
    .map((row) => ({
      startSec: Number(row?.start_sec),
      endSec: Number(row?.end_sec),
      anomalyFlag: String(row?.anomaly_flag || "").trim().toLowerCase() === "oui",
    }))
    .filter((row) => Number.isFinite(row.startSec) && Number.isFinite(row.endSec) && row.anomalyFlag);

  return segmentRows.map((segmentRow, index) => {
    const startSec = Number(segmentRow?.start_sec);
    const endSecRaw = Number(segmentRow?.end_sec);
    const normalizedStart = Number.isFinite(startSec) ? startSec : 0;
    const normalizedEnd = Number.isFinite(endSecRaw) ? endSecRaw : normalizedStart;
    const timestampSync = (normalizedStart + normalizedEnd) / 2;
    const framesInSegment = motionRows.filter((row) => {
      const rowTime = Number(row?.time_sec);
      return Number.isFinite(rowTime) && rowTime >= normalizedStart && rowTime <= normalizedEnd;
    });
    const nearestMotion = getClosestMotionRowByTime(motionRows, timestampSync);
    const nearestFrameTime = Number(nearestMotion?.time_sec);
    const nearestFrameId = Number(nearestMotion?.frame_index);
    const anomalyAudio = anomalyRows.some(
      (anomaly) => timestampSync >= anomaly.startSec && timestampSync <= anomaly.endSec
    );

    return {
      ...segmentRow,
      segment_id: String(segmentRow?.segment_id || segmentRow?.segmentId || index + 1),
      timestamp_sync: Number.isFinite(timestampSync) ? timestampSync.toFixed(6) : "",
      frame_count_sync: String(framesInSegment.length),
      first_frame_id_sync: framesInSegment[0]?.frame_index ?? "",
      first_frame_path_sync: framesInSegment[0]?.image_path || framesInSegment[0]?.frame_preview_path || "",
      last_frame_id_sync: framesInSegment.at(-1)?.frame_index ?? "",
      last_frame_path_sync: framesInSegment.at(-1)?.image_path || framesInSegment.at(-1)?.frame_preview_path || "",
      nearest_frame_id_sync: Number.isFinite(nearestFrameId) ? String(nearestFrameId) : "",
      nearest_frame_path_sync: nearestMotion?.image_path || nearestMotion?.frame_preview_path || "",
      nearest_frame_time_sec_sync: Number.isFinite(nearestFrameTime) ? nearestFrameTime.toFixed(6) : "",
      anomalie_audio_sync: anomalyAudio ? "oui" : "non",
    };
  });
}

function buildAlignmentTimelineDataFromRows(alignedRows, motionRows, anomalyRows, pauseRows = null) {
  const safeAlignedRows = Array.isArray(alignedRows) ? alignedRows : [];
  const safeMotionRows = Array.isArray(motionRows) ? motionRows : [];
  const safeAnomalyRows = Array.isArray(anomalyRows) ? anomalyRows : [];
  const safePauseRows = Array.isArray(pauseRows) ? pauseRows : [];

  const imageItems = safeMotionRows
    .map((row) => ({
      time_sec: Number(row?.time_sec),
      frame_index: Number(row?.frame_index),
      motion_mean: Number(row?.motion_mean),
      roi_directional_entropy: Number(row?.roi_directional_entropy),
      direction_label: String(row?.direction_label || "").trim(),
      row,
    }))
    .filter((item) => Number.isFinite(item.time_sec))
    .sort((left, right) => left.time_sec - right.time_sec);

  const frameTimeByIndex = new Map(
    imageItems
      .filter((item) => Number.isFinite(item.frame_index))
      .map((item) => [Number(item.frame_index), Number(item.time_sec)])
  );
  const frameDiffs = [];
  for (let index = 1; index < imageItems.length; index += 1) {
    const previousTime = Number(imageItems[index - 1]?.time_sec);
    const currentTime = Number(imageItems[index]?.time_sec);
    const diff = currentTime - previousTime;
    if (Number.isFinite(diff) && diff > 0) {
      frameDiffs.push(diff);
    }
  }
  const frameStepSec = frameDiffs.length
    ? frameDiffs.sort((left, right) => left - right)[Math.floor(frameDiffs.length / 2)]
    : 0;

  const textItems = safeAlignedRows
    .map((row) => ({
      segment_id: String(row?.segment_id || "").trim(),
      start_sec: Number(row?.start_sec),
      end_sec: Number(row?.end_sec),
      first_frame_id_sync: Number(row?.first_frame_id_sync),
      last_frame_id_sync: Number(row?.last_frame_id_sync),
      timestamp_sync: Number(row?.timestamp_sync),
      text: String(row?.text || "").trim(),
      anomalie_audio_sync: String(row?.anomalie_audio_sync || "").trim().toLowerCase(),
      pause_before_sec: Number(row?.pause_before_sec),
      pause_after_sec: Number(row?.pause_after_sec),
      word_timestamps_json: String(row?.word_timestamps_json || "").trim(),
      word_items: getAlignmentWordItems(row),
      row,
    }))
    .filter((item) => Number.isFinite(item.start_sec) && Number.isFinite(item.end_sec))
    .map((item) => {
      const pauseBeforeSec = Number.isFinite(item.pause_before_sec) && item.pause_before_sec > 0
        ? item.pause_before_sec
        : 0;
      const pauseAfterSec = Number.isFinite(item.pause_after_sec) && item.pause_after_sec > 0
        ? item.pause_after_sec
        : 0;
      const contextStartSec = Math.max(0, item.start_sec - pauseBeforeSec);
      const contextEndSec = item.end_sec + pauseAfterSec;
      const directFrameTimes = [
        frameTimeByIndex.get(Number(item.first_frame_id_sync)),
        frameTimeByIndex.get(Number(item.last_frame_id_sync)),
      ].filter((value) => Number.isFinite(value));
      const overlappingFrameTimes = imageItems
        .filter((frame) => Number(frame.time_sec) >= item.start_sec && Number(frame.time_sec) <= item.end_sec)
        .map((frame) => Number(frame.time_sec))
        .filter((value) => Number.isFinite(value));
      const candidateFrameTimes = directFrameTimes.length ? directFrameTimes : overlappingFrameTimes;
      const visualStartSec = candidateFrameTimes.length
        ? Math.min(...candidateFrameTimes)
        : item.start_sec;
      const visualEndBaseSec = candidateFrameTimes.length
        ? Math.max(...candidateFrameTimes)
        : item.end_sec;
      const visualEndSec = candidateFrameTimes.length && frameStepSec > 0
        ? Math.min(item.end_sec, visualEndBaseSec + frameStepSec)
        : item.end_sec;
      return {
        ...item,
        speech_duration_sec: Math.max(0, item.end_sec - item.start_sec),
        context_start_sec: contextStartSec,
        context_end_sec: contextEndSec,
        context_duration_sec: Math.max(0, contextEndSec - contextStartSec),
        visual_start_sec: visualStartSec,
        visual_end_sec: Math.max(visualStartSec, visualEndSec),
      };
    })
    .sort((left, right) => left.start_sec - right.start_sec);

  const pauseItems = safePauseRows.length
    ? safePauseRows
      .map((row) => ({
        kind: "silence",
        pause_id: Number(row?.pause_id),
        start_sec: Number(row?.start_sec),
        end_sec: Number(row?.end_sec),
        duration_sec: Number(row?.duration_sec),
      }))
      .filter((item) => Number.isFinite(item.start_sec) && Number.isFinite(item.end_sec) && item.end_sec > item.start_sec)
    : [];
  if (!pauseItems.length) {
    safeAlignedRows.forEach((row) => {
      const startSec = Number(row?.start_sec);
      const endSec = Number(row?.end_sec);
      const segmentId = String(row?.segment_id || "").trim();
      const pauseBeforeSec = Number(row?.pause_before_sec);
      if (Number.isFinite(startSec) && Number.isFinite(pauseBeforeSec) && pauseBeforeSec > 0) {
        pauseItems.push({
          kind: "before",
          segment_id: segmentId,
          start_sec: Math.max(0, startSec - pauseBeforeSec),
          end_sec: startSec,
          duration_sec: pauseBeforeSec,
        });
      }
      const pauseAfterSec = Number(row?.pause_after_sec);
      if (Number.isFinite(endSec) && Number.isFinite(pauseAfterSec) && pauseAfterSec > 0) {
        pauseItems.push({
          kind: "after",
          segment_id: segmentId,
          start_sec: endSec,
          end_sec: endSec + pauseAfterSec,
          duration_sec: pauseAfterSec,
        });
      }
    });
  }
  pauseItems.sort((left, right) => Number(left.start_sec || 0) - Number(right.start_sec || 0));

  const audioItems = safeAnomalyRows
    .map((row) => ({
      start_sec: Number(row?.start_sec),
      end_sec: Number(row?.end_sec),
      time_sec: Number(row?.time_sec),
      z_score: Number(row?.z_score),
      anomaly_flag: String(row?.anomaly_flag || "").trim().toLowerCase(),
      row,
    }))
    .filter((item) =>
      item.anomaly_flag === "oui"
      && Number.isFinite(item.start_sec)
      && Number.isFinite(item.end_sec)
    )
    .sort((left, right) => left.start_sec - right.start_sec);

  const durationCandidates = [
    ...imageItems.map((item) => item.time_sec),
    ...textItems.map((item) => item.end_sec),
    ...pauseItems.map((item) => item.end_sec),
    ...audioItems.map((item) => item.end_sec),
    ...textItems.map((item) => Number(item?.timestamp_sync) || ((Number(item?.start_sec) + Number(item?.end_sec)) / 2)),
    ...audioItems.map((item) => Number(item?.time_sec) || 0),
  ].filter((value) => Number.isFinite(value));
  const imageTimeValues = imageItems
    .map((item) => Number(item?.time_sec))
    .filter((value) => Number.isFinite(value));
  const firstImageTimeSec = imageTimeValues.length ? imageTimeValues[0] : Number.NaN;
  const lastImageTimeSec = imageTimeValues.length ? imageTimeValues[imageTimeValues.length - 1] : Number.NaN;
  const duration_sec = Number.isFinite(lastImageTimeSec) && lastImageTimeSec > 0
    ? lastImageTimeSec
    : (durationCandidates.length ? Math.max(...durationCandidates) : 0);
  const speechRateTrack = ensureTimelineTrackPointAtTime(
    prependTimelineTrackAnchor(
      textItems
        .flatMap((item) => {
          const startSec = Number(item?.start_sec);
          const endSec = Number(item?.end_sec);
          const value = Number(item?.row?.words_per_sec ?? item?.words_per_sec);
          const label = item.segment_id ? `segment ${item.segment_id}` : "segment";
          if (!Number.isFinite(startSec) || !Number.isFinite(value)) {
            return [];
          }
          const points = [
            {
              time_sec: startSec,
              value,
              label,
              row: item.row,
            },
          ];
          if (Number.isFinite(endSec) && endSec > startSec) {
            points.push({
              time_sec: endSec,
              value,
              label,
              row: item.row,
            });
          }
          return points;
        })
        .filter((item) => Number.isFinite(item.time_sec) && Number.isFinite(item.value)),
      firstImageTimeSec,
    ),
    firstImageTimeSec,
  );
  const motionTrack = prependTimelineTrackAnchor(
    imageItems
      .filter((item) => Number.isFinite(item.motion_mean))
      .map((item) => ({
        time_sec: item.time_sec,
        value: item.motion_mean,
        frame_index: item.frame_index,
        label: item.direction_label,
        row: item.row,
      })),
    firstImageTimeSec,
  );
  const entropyTrack = prependTimelineTrackAnchor(
    imageItems
      .filter((item) => Number.isFinite(item.roi_directional_entropy))
      .map((item) => ({
        time_sec: item.time_sec,
        value: item.roi_directional_entropy,
        frame_index: item.frame_index,
        label: item.direction_label,
        row: item.row,
      })),
    firstImageTimeSec,
  );

  return {
    duration_sec,
    tracks: {
      images: imageItems,
      text: textItems,
      pauses: pauseItems,
      audio_anomalies: audioItems,
      speech_rate: speechRateTrack,
      motion_mean: motionTrack,
      directional_entropy: entropyTrack,
    },
  };
}

function resolveTextTrackPauseLayout(item, pauseItems = [], durationSec = 0) {
  const speechStartSec = Number(item?.start_sec);
  const speechEndSec = Number(item?.end_sec);
  if (!Number.isFinite(speechStartSec) || !Number.isFinite(speechEndSec)) {
    return null;
  }

  const pauseBeforeFallback = Number.isFinite(Number(item?.pause_before_sec)) && Number(item.pause_before_sec) > 0
    ? Number(item.pause_before_sec)
    : 0;
  const pauseAfterFallback = Number.isFinite(Number(item?.pause_after_sec)) && Number(item.pause_after_sec) > 0
    ? Number(item.pause_after_sec)
    : 0;
  const contextStartSec = Number.isFinite(Number(item?.context_start_sec))
    ? Number(item.context_start_sec)
    : Math.max(0, speechStartSec - pauseBeforeFallback);
  const contextEndSec = Number.isFinite(Number(item?.context_end_sec))
    ? Number(item.context_end_sec)
    : speechEndSec + pauseAfterFallback;
  const toleranceSec = 0.35;

  const normalizedPauses = Array.isArray(pauseItems)
    ? pauseItems
      .map((pause) => ({
        ...pause,
        start_sec: Number(pause?.start_sec),
        end_sec: Number(pause?.end_sec),
      }))
      .filter((pause) => Number.isFinite(pause.start_sec) && Number.isFinite(pause.end_sec) && pause.end_sec > pause.start_sec)
    : [];

  const beforeCandidates = normalizedPauses.filter((pause) =>
    pause.end_sec >= contextStartSec - toleranceSec
    && pause.end_sec <= speechStartSec + toleranceSec
    && pause.start_sec < speechStartSec
  );
  const afterCandidates = normalizedPauses.filter((pause) =>
    pause.start_sec <= contextEndSec + toleranceSec
    && pause.start_sec >= speechEndSec - toleranceSec
    && pause.end_sec > speechEndSec
  );

  let beforePause = null;
  if (beforeCandidates.length) {
    const candidate = beforeCandidates.sort((left, right) => right.end_sec - left.end_sec)[0];
    beforePause = {
      startSec: Math.max(0, Math.min(candidate.start_sec, speechStartSec)),
      endSec: Math.min(speechStartSec, candidate.end_sec),
    };
  } else if (pauseBeforeFallback > 0) {
    beforePause = {
      startSec: Math.max(0, speechStartSec - pauseBeforeFallback),
      endSec: speechStartSec,
    };
  }

  let afterPause = null;
  if (afterCandidates.length) {
    const candidate = afterCandidates.sort((left, right) => left.start_sec - right.start_sec)[0];
    afterPause = {
      startSec: Math.max(speechEndSec, candidate.start_sec),
      endSec: candidate.end_sec,
    };
  } else if (pauseAfterFallback > 0) {
    afterPause = {
      startSec: speechEndSec,
      endSec: speechEndSec + pauseAfterFallback,
    };
  }

  if (beforePause && beforePause.endSec <= beforePause.startSec) {
    beforePause = null;
  }
  if (afterPause && afterPause.endSec <= afterPause.startSec) {
    afterPause = null;
  }

  let pauseSegments = normalizedPauses
    .filter((pause) =>
      pause.start_sec < contextEndSec + toleranceSec
      && pause.end_sec > contextStartSec - toleranceSec
    )
    .map((pause) => ({
      startSec: Math.max(0, Math.max(contextStartSec, pause.start_sec)),
      endSec: Math.max(0, Math.min(contextEndSec, pause.end_sec)),
    }))
    .filter((pause) => pause.endSec > pause.startSec);

  if (!pauseSegments.length) {
    pauseSegments = [beforePause, afterPause].filter(Boolean);
  }

  pauseSegments = mergePauseSegmentsForDisplay(pauseSegments);

  const laneStartSec = Math.max(0, Math.min(beforePause?.startSec ?? speechStartSec, speechStartSec));
  const laneEndSec = Math.min(
    Math.max(durationSec || 0, speechEndSec),
    Math.max(speechEndSec, afterPause?.endSec ?? speechEndSec),
  );

  return {
    laneStartSec,
    laneEndSec: Math.max(laneStartSec, laneEndSec),
    speechStartSec,
    speechEndSec,
    beforePause,
    afterPause,
    pauseSegments,
  };
}

function getParsedAlignmentRows() {
  const alignResult = appState.multimodalResults?.alignement;
  const alignmentArtifact = alignResult?.alignmentCsvArtifact;
  if (!alignmentArtifact) {
    const derivedRows = buildDerivedAlignmentRows();
    return derivedRows.length ? derivedRows : null;
  }

  const parsed = parseCsv(artifactDataToText(alignmentArtifact));
  if (!parsed?.headers?.length || !Array.isArray(parsed.rows) || !parsed.rows.length) {
    const derivedRows = buildDerivedAlignmentRows();
    return derivedRows.length ? derivedRows : null;
  }

  return parsed.rows.map((row) => {
    const mapped = {};
    parsed.headers.forEach((header, index) => {
      mapped[header] = row[index];
    });
    return mapped;
  });
}

function getSelectedAlignmentTimelineScale() {
  const value = Number(multimodalAlignTimelineScale?.value || 130);
  if (!Number.isFinite(value)) return 130;
  return Math.max(60, Math.min(220, value));
}

function getSelectedAlignmentCurveMode() {
  return "raw";
}

function buildDerivedAlignmentTimelineData() {
  const alignedRows = getParsedAlignmentRows() || [];
  const motionRows = getParsedMotionRows() || [];
  const anomalyRows = getParsedAudioAnomalyRows() || [];
  const pauseRows = getParsedAudioPauseRows() || [];
  return buildAlignmentTimelineDataFromRows(alignedRows, motionRows, anomalyRows, pauseRows);
}

function getParsedAlignmentTimelineData() {
  if (getParsedAudioPauseRows().length) {
    return buildDerivedAlignmentTimelineData();
  }
  const artifact = appState.multimodalResults?.alignement?.timelineJsonArtifact;
  if (artifact) {
    try {
      const parsed = JSON.parse(artifactDataToText(artifact));
      if (parsed && typeof parsed === "object") {
        if (parsed?.tracks?.pauses) {
          return parsed;
        }
      }
    } catch (_error) {
      // Fallback sur la reconstruction depuis les CSV.
    }
  }
  return buildDerivedAlignmentTimelineData();
}

function getParsedMotionRows() {
  const motionResult = appState.multimodalResults?.mouvements;
  const framesArtifact = motionResult?.framesCsvArtifact;
  if (!framesArtifact) return null;

  const parsed = parseCsv(artifactDataToText(framesArtifact));
  if (!parsed?.headers?.length || !Array.isArray(parsed.rows) || !parsed.rows.length) {
    return null;
  }

  return parsed.rows.map((row) => {
    const mapped = {};
    parsed.headers.forEach((header, index) => {
      mapped[header] = row[index];
    });
    return mapped;
  });
}

function getSelectedAlignmentImageView() {
  const value = String(multimodalAlignImageView?.value || "brute").trim().toLowerCase();
  return ["brute", "magnitude", "entropie", "hsv", "vecteurs", "superposition", "anatomie"].includes(value)
    ? value
    : "brute";
}

function getAlignmentImageViewConfig(view) {
  const configs = {
    brute: { label: "Image brute", motionPathKey: "frame_preview_path" },
    magnitude: { label: "Magnitude", motionPathKey: "magnitude_preview_path" },
    entropie: { label: "Entropie directionnelle", motionPathKey: "directional_entropy_preview_path" },
    hsv: { label: "HSV", motionPathKey: "hsv_preview_path" },
    vecteurs: { label: "Vecteurs", motionPathKey: "vectors_preview_path" },
    superposition: { label: "Superposition", motionPathKey: "overlay_preview_path" },
    anatomie: { label: "Annotée", motionPathKey: "annotated_preview_path" },
  };
  return configs[view] || configs.brute;
}

function getAlignmentFramePathCandidates(row) {
  const unique = [];
  [
    row?.nearest_frame_path_sync,
    row?.first_frame_path_sync,
    row?.last_frame_path_sync,
  ].forEach((value) => {
    const trimmed = String(value || "").trim();
    if (trimmed && !unique.includes(trimmed)) {
      unique.push(trimmed);
    }
  });
  return unique;
}

function findMotionRowForAlignmentRow(row, motionRows) {
  if (!Array.isArray(motionRows) || !motionRows.length) return null;

  const absoluteCandidates = getAlignmentFramePathCandidates(row).map((value) => normalizePath(value));
  const basenameCandidates = absoluteCandidates.map((value) => value.split("/").pop() || value);
  if (!absoluteCandidates.length) return null;

  return motionRows.find((motionRow) => {
    const rowCandidates = [
      motionRow?.image_path,
      motionRow?.frame_preview_path,
      motionRow?.magnitude_preview_path,
      motionRow?.directional_entropy_preview_path,
      motionRow?.hsv_preview_path,
      motionRow?.vectors_preview_path,
      motionRow?.overlay_preview_path,
      motionRow?.annotated_preview_path,
    ]
      .map((value) => String(value || "").trim())
      .filter(Boolean);

    return rowCandidates.some((candidate) => {
      const normalized = normalizePath(candidate);
      const basename = normalized.split("/").pop() || normalized;
      return absoluteCandidates.includes(normalized) || basenameCandidates.includes(basename);
    });
  }) || null;
}

function resolveAlignmentImageSource(row, requestedView, motionRows = null) {
  const alignResult = appState.multimodalResults?.alignement;
  const motionResult = appState.multimodalResults?.mouvements;
  const config = getAlignmentImageViewConfig(requestedView);
  const motionRow = findMotionRowForAlignmentRow(row, motionRows);
  const rawCandidates = getAlignmentFramePathCandidates(row);

  let absolutePath = "";
  let artifactOwner = null;
  let outputDir = "";
  let effectiveLabel = config.label;
  let fallbackNote = "";

  const motionPath = motionRow ? String(motionRow?.[config.motionPathKey] || "").trim() : "";
  if (motionPath) {
    absolutePath = motionPath;
    artifactOwner = motionResult?.artifacts || [];
    outputDir = motionResult?.outputDir || "";
  } else {
    absolutePath = rawCandidates[0] || "";
    artifactOwner = alignResult?.files || [];
    outputDir = alignResult?.outputDir || "";
    if (requestedView !== "brute") {
      effectiveLabel = "Image brute";
      fallbackNote = "Vue demandée indisponible pour cette image, image brute affichée.";
    }
  }

  const artifact = absolutePath ? findArtifactForAbsolutePath(artifactOwner, outputDir, absolutePath) : null;
  const src = artifact ? artifactDataToObjectUrl(artifact) : maybeCreateLocalFileUrl(absolutePath);

  return {
    src,
    absolutePath,
    label: effectiveLabel,
    fallbackNote,
  };
}

function resolveAlignmentImageSourceForMotionRow(motionRow, requestedView) {
  const motionResult = appState.multimodalResults?.mouvements;
  const config = getAlignmentImageViewConfig(requestedView);
  const fallbackPath = String(motionRow?.frame_preview_path || motionRow?.image_path || "").trim();
  const requestedPath = String(motionRow?.[config.motionPathKey] || "").trim();
  const absolutePath = requestedPath || fallbackPath;
  const effectiveLabel = requestedPath ? config.label : "Image brute";
  const fallbackNote = requestedPath || requestedView === "brute"
    ? ""
    : "Vue demandée indisponible pour cette image, image brute affichée.";
  const artifact = absolutePath
    ? findArtifactForAbsolutePath(motionResult?.artifacts || [], motionResult?.outputDir || "", absolutePath)
    : null;
  const src = artifact ? artifactDataToObjectUrl(artifact) : maybeCreateLocalFileUrl(absolutePath);
  return {
    src,
    absolutePath,
    label: effectiveLabel,
    fallbackNote,
  };
}

function getAlignedWordMatches(text) {
  return Array.from(String(text || "").matchAll(/[A-Za-zÀ-ÿ0-9'’-]+/g));
}

function getAlignmentHighlightedWordIndex(row, targetTimeOverride = null) {
  const wordItems = getAlignmentWordItems(row);
  const overrideTime = Number(targetTimeOverride);
  const nearestTime = Number(row?.nearest_frame_time_sec_sync);
  const targetTime = Number.isFinite(overrideTime)
    ? overrideTime
    : (Number.isFinite(nearestTime) ? nearestTime : NaN);
  if (wordItems.length && Number.isFinite(targetTime)) {
    const matchingIndex = wordItems.findIndex((item) => targetTime >= Number(item.start_sec) && targetTime <= Number(item.end_sec));
    if (matchingIndex >= 0) {
      return matchingIndex;
    }
    let bestIndex = 0;
    let bestDelta = Number.POSITIVE_INFINITY;
    wordItems.forEach((item, index) => {
      const midpoint = (Number(item.start_sec) + Number(item.end_sec)) / 2;
      const delta = Math.abs(midpoint - targetTime);
      if (delta < bestDelta) {
        bestDelta = delta;
        bestIndex = index;
      }
    });
    return bestIndex;
  }

  const text = String(row?.text || "").trim();
  const matches = getAlignedWordMatches(text);
  if (!matches.length) return -1;

  const startSec = Number(row?.start_sec);
  const endSec = Number(row?.end_sec);

  if (!Number.isFinite(startSec) || !Number.isFinite(endSec) || endSec <= startSec) {
    return 0;
  }

  const fallbackTargetTime = Number.isFinite(targetTime)
    ? targetTime
    : ((startSec + endSec) / 2);
  const normalized = Math.min(0.999999, Math.max(0, (fallbackTargetTime - startSec) / (endSec - startSec)));
  return Math.max(0, Math.min(matches.length - 1, Math.floor(normalized * matches.length)));
}

function createHighlightedAlignmentText(row, targetTimeOverride = null) {
  const text = String(row?.text || "").trim();
  const paragraph = document.createElement("p");
  paragraph.className = "multimodal-segment-sync-text-caption";

  if (!text) {
    paragraph.textContent = "[Segment sans texte]";
    return paragraph;
  }

  const matches = getAlignedWordMatches(text);
  const highlightedIndex = getAlignmentHighlightedWordIndex(row, targetTimeOverride);
  if (!matches.length || highlightedIndex < 0) {
    paragraph.textContent = text;
    return paragraph;
  }

  let cursor = 0;
  matches.forEach((match, index) => {
    const word = String(match[0] || "");
    const start = Number(match.index || 0);
    const end = start + word.length;
    if (start > cursor) {
      paragraph.appendChild(document.createTextNode(text.slice(cursor, start)));
    }
    if (index === highlightedIndex) {
      const mark = document.createElement("mark");
      mark.className = "multimodal-segment-sync-highlight";
      mark.textContent = word;
      paragraph.appendChild(mark);
    } else {
      paragraph.appendChild(document.createTextNode(word));
    }
    cursor = end;
  });
  if (cursor < text.length) {
    paragraph.appendChild(document.createTextNode(text.slice(cursor)));
  }
  return paragraph;
}

function truncateTimelineText(text, maxLength = 120) {
  const value = String(text || "").trim();
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function assignTimelineTokenLanes(tokens, pxPerSecond) {
  const laneEnds = [0, 0, 0];
  return tokens.map((token) => {
    const startSec = Number(token?.start_sec);
    const endSec = Number(token?.end_sec);
    const leftPx = Math.max(0, (startSec - Number(token.base_start_sec || 0)) * pxPerSecond);
    const widthPx = Math.max(
      token.kind === "pause" ? 34 : 22,
      Math.max(0, endSec - startSec) * pxPerSecond
    );
    let chosenLane = 0;
    let bestGap = Number.POSITIVE_INFINITY;
    laneEnds.forEach((laneEnd, laneIndex) => {
      const gap = Math.abs(leftPx - laneEnd);
      if (leftPx >= laneEnd - 6) {
        chosenLane = laneIndex;
        bestGap = -1;
        return;
      }
      if (bestGap >= 0 && gap < bestGap) {
        chosenLane = laneIndex;
        bestGap = gap;
      }
    });
    laneEnds[chosenLane] = leftPx + widthPx + 6;
    return {
      ...token,
      lane: chosenLane,
      leftPx,
      widthPx,
    };
  });
}

function buildReadablePauseLabel(durationSec) {
  const duration = Number(durationSec);
  if (!Number.isFinite(duration) || duration <= 0) return "pause audio";
  return `pause audio (${duration.toFixed(2)} s)`;
}

function getReadableTokenSeparator(previousToken, currentToken) {
  if (!previousToken || !currentToken) return "";
  if (previousToken.kind === "pause" || currentToken.kind === "pause") {
    return " - ";
  }
  const previousLabel = String(previousToken.label || "");
  const currentLabel = String(currentToken.label || "");
  if (currentLabel.startsWith("-") || previousLabel.endsWith("-")) {
    return "";
  }
  if (currentLabel.startsWith("'") || currentLabel.startsWith("’")) {
    return "";
  }
  if (previousLabel.endsWith("'") || previousLabel.endsWith("’")) {
    return "";
  }
  return " ";
}

function prependTimelineTrackAnchor(items, anchorTimeSec) {
  if (!Array.isArray(items) || !items.length) return items;
  const firstItem = items[0];
  const firstTimeSec = Number(firstItem?.time_sec);
  const normalizedAnchorSec = Number(anchorTimeSec);
  if (!Number.isFinite(normalizedAnchorSec) || !Number.isFinite(firstTimeSec) || normalizedAnchorSec >= firstTimeSec) {
    return items;
  }
  return [
    {
      ...firstItem,
      time_sec: normalizedAnchorSec,
    },
    ...items,
  ];
}

function ensureTimelineTrackPointAtTime(items, anchorTimeSec) {
  if (!Array.isArray(items) || !items.length) return items;
  const normalizedAnchorSec = Number(anchorTimeSec);
  if (!Number.isFinite(normalizedAnchorSec)) return items;

  const sortedItems = [...items].sort((left, right) => Number(left?.time_sec || 0) - Number(right?.time_sec || 0));
  if (sortedItems.some((item) => Math.abs(Number(item?.time_sec) - normalizedAnchorSec) < 0.000001)) {
    return sortedItems;
  }

  let carryItem = null;
  for (let index = 0; index < sortedItems.length; index += 1) {
    const current = sortedItems[index];
    const currentTimeSec = Number(current?.time_sec);
    const next = sortedItems[index + 1] || null;
    const nextTimeSec = Number(next?.time_sec);
    if (!Number.isFinite(currentTimeSec)) continue;
    if (currentTimeSec <= normalizedAnchorSec && (!Number.isFinite(nextTimeSec) || nextTimeSec >= normalizedAnchorSec)) {
      carryItem = current;
      break;
    }
  }

  if (!carryItem) {
    carryItem = sortedItems.find((item) => Number(item?.time_sec) >= normalizedAnchorSec) || sortedItems[sortedItems.length - 1];
  }
  if (!carryItem) {
    return sortedItems;
  }

  return [
    ...sortedItems,
    {
      ...carryItem,
      time_sec: normalizedAnchorSec,
    },
  ].sort((left, right) => Number(left?.time_sec || 0) - Number(right?.time_sec || 0));
}

function mergePauseSegmentsForDisplay(segments, gapToleranceSec = 0.08) {
  if (!Array.isArray(segments) || !segments.length) return [];
  const sorted = segments
    .map((segment) => ({
      ...segment,
      startSec: Number(segment?.startSec ?? segment?.start_sec),
      endSec: Number(segment?.endSec ?? segment?.end_sec),
    }))
    .filter((segment) => Number.isFinite(segment.startSec) && Number.isFinite(segment.endSec) && segment.endSec > segment.startSec)
    .sort((left, right) => left.startSec - right.startSec);

  if (!sorted.length) return [];

  const merged = [sorted[0]];
  for (let index = 1; index < sorted.length; index += 1) {
    const current = sorted[index];
    const previous = merged[merged.length - 1];
    if (current.startSec <= previous.endSec + gapToleranceSec) {
      previous.endSec = Math.max(previous.endSec, current.endSec);
      continue;
    }
    merged.push(current);
  }
  return merged;
}

function buildAlignmentReadableSpeechTokens(item, layout) {
  const speechStartSec = Number(layout?.speechStartSec);
  const speechEndSec = Number(layout?.speechEndSec);
  const wordItems = getAlignmentWordItems(item)
    .map((word, index) => ({
      kind: "word",
      order: index,
      start_sec: Number(word?.start_sec),
      end_sec: Number(word?.end_sec),
      label: String(word?.word || "").trim(),
    }))
    .filter((token) =>
      Number.isFinite(token.start_sec)
      && Number.isFinite(token.end_sec)
      && token.label
      && token.end_sec >= speechStartSec
      && token.start_sec <= speechEndSec
    );

  const pauseTokens = (Array.isArray(layout?.pauseSegments) ? layout.pauseSegments : [])
    .map((pause, index) => {
      const startSec = Math.max(speechStartSec, Number(pause?.startSec));
      const endSec = Math.min(speechEndSec, Number(pause?.endSec));
      const durationSec = Math.max(0, endSec - startSec);
      return {
        kind: "pause",
        order: index,
        start_sec: startSec,
        end_sec: endSec,
        duration_sec: durationSec,
        label: buildReadablePauseLabel(durationSec),
      };
    })
    .filter((token) => Number.isFinite(token.start_sec) && Number.isFinite(token.end_sec) && token.end_sec > token.start_sec);

  return [...wordItems, ...pauseTokens].sort((left, right) => {
    if (left.start_sec !== right.start_sec) {
      return left.start_sec - right.start_sec;
    }
    if (left.kind !== right.kind) {
      return left.kind === "pause" ? -1 : 1;
    }
    return left.order - right.order;
  });
}

function createAlignmentReadableTextLine(item, layout, targetTimeOverride = null) {
  const line = document.createElement("div");
  line.className = "multimodal-timeline-readable-text";
  const tokens = buildAlignmentReadableSpeechTokens(item, layout);
  if (!tokens.length) {
    line.textContent = truncateTimelineText(item?.text || "", 220);
    return line;
  }

  const highlightedWordIndex = getAlignmentHighlightedWordIndex(item, targetTimeOverride);
  let runningWordIndex = -1;
  tokens.forEach((token, index) => {
    if (index > 0) {
      line.appendChild(document.createTextNode(getReadableTokenSeparator(tokens[index - 1], token)));
    }
    if (token.kind === "pause") {
      const chip = document.createElement("span");
      chip.className = "multimodal-timeline-readable-token multimodal-timeline-readable-token--pause";
      chip.textContent = token.label;
      line.appendChild(chip);
    } else {
      runningWordIndex += 1;
      const chip = runningWordIndex === highlightedWordIndex
        ? document.createElement("mark")
        : document.createElement("span");
      chip.className = "multimodal-timeline-readable-token";
      if (runningWordIndex === highlightedWordIndex) {
        chip.classList.add("is-current");
      }
      chip.textContent = token.label;
      line.appendChild(chip);
    }
  });
  return line;
}

function createAlignmentTimedTextSlots(item, layout, imageItems, pxPerSecond) {
  const speechStartSec = Number(layout?.speechStartSec);
  const speechEndSec = Number(layout?.speechEndSec);
  if (!Number.isFinite(speechStartSec) || !Number.isFinite(speechEndSec) || speechEndSec <= speechStartSec) {
    return null;
  }

  const relevantTimes = Array.from(new Set(
    (Array.isArray(imageItems) ? imageItems : [])
      .map((image) => Number(image?.time_sec))
      .filter((timeSec) => Number.isFinite(timeSec) && timeSec >= speechStartSec && timeSec <= speechEndSec)
      .map((timeSec) => Number(timeSec.toFixed(6)))
  )).sort((left, right) => left - right);

  if (!relevantTimes.length) {
    return null;
  }

  const tokens = buildAlignmentReadableSpeechTokens(item, layout).map((token) => ({
    ...token,
    midpointSec: (Number(token.start_sec) + Number(token.end_sec)) / 2,
  }));

  const container = document.createElement("div");
  container.className = "multimodal-timeline-text-slots";

  relevantTimes.forEach((timeSec, index) => {
    const previousTimeSec = index > 0 ? relevantTimes[index - 1] : speechStartSec;
    const nextTimeSec = index < relevantTimes.length - 1 ? relevantTimes[index + 1] : speechEndSec;
    const slotStartSec = Math.max(speechStartSec, index > 0 ? (previousTimeSec + timeSec) / 2 : speechStartSec);
    const slotEndSec = Math.min(speechEndSec, index < relevantTimes.length - 1 ? (timeSec + nextTimeSec) / 2 : speechEndSec);
    if (!Number.isFinite(slotStartSec) || !Number.isFinite(slotEndSec) || slotEndSec <= slotStartSec) {
      return;
    }

    const slotTokens = tokens.filter((token) => {
      if (token.kind === "pause") {
        return Number(token.end_sec) > slotStartSec && Number(token.start_sec) < slotEndSec;
      }
      if (!Number.isFinite(token.midpointSec)) return false;
      if (index === relevantTimes.length - 1) {
        return token.midpointSec >= slotStartSec && token.midpointSec <= slotEndSec;
      }
      return token.midpointSec >= slotStartSec && token.midpointSec < slotEndSec;
    });

    const slot = document.createElement("div");
    slot.className = "multimodal-timeline-text-slot";
    slot.style.left = `${Math.max(0, (slotStartSec - speechStartSec) * pxPerSecond)}px`;
    slot.style.width = `${Math.max(44, (slotEndSec - slotStartSec) * pxPerSecond)}px`;
    slot.title = `image ${timeSec.toFixed(2)} s · ${slotStartSec.toFixed(2)} s → ${slotEndSec.toFixed(2)} s`;

    if (!slotTokens.length) {
      const fallbackPauseDurationSec = Math.max(0, slotEndSec - slotStartSec);
      if (fallbackPauseDurationSec >= 0.04) {
        const pauseChip = document.createElement("span");
        pauseChip.className = "multimodal-timeline-readable-token multimodal-timeline-readable-token--pause";
        pauseChip.textContent = buildReadablePauseLabel(fallbackPauseDurationSec);
        slot.appendChild(pauseChip);
      }
      container.appendChild(slot);
      return;
    }

    slotTokens.forEach((token, tokenIndex) => {
      if (tokenIndex > 0) {
        slot.appendChild(document.createTextNode(getReadableTokenSeparator(slotTokens[tokenIndex - 1], token)));
      }
      if (token.kind === "pause") {
        const pauseChip = document.createElement("span");
        pauseChip.className = "multimodal-timeline-readable-token multimodal-timeline-readable-token--pause";
        pauseChip.textContent = token.label;
        slot.appendChild(pauseChip);
      } else {
        const word = document.createElement("span");
        word.className = "multimodal-timeline-readable-token";
        word.textContent = token.label;
        slot.appendChild(word);
      }
    });

    container.appendChild(slot);
  });

  return container.childNodes.length ? container : null;
}

function renderStandalonePausesInTextLane(lane, pauseItems, textItems, pxPerSecond, displayDurationSec, trackHeight) {
  if (!lane || !Array.isArray(pauseItems) || !pauseItems.length) return;
  const speechIntervals = (Array.isArray(textItems) ? textItems : [])
    .map((item) => ({
      startSec: Number(item?.start_sec),
      endSec: Number(item?.end_sec),
    }))
    .filter((item) => Number.isFinite(item.startSec) && Number.isFinite(item.endSec) && item.endSec > item.startSec);

  mergePauseSegmentsForDisplay(
    pauseItems.map((item) => ({
      ...item,
      startSec: Number(item?.start_sec),
      endSec: Number(item?.end_sec),
    }))
  ).forEach((pause) => {
    const startSec = Number(pause?.startSec ?? pause?.start_sec);
    const endSec = Number(pause?.endSec ?? pause?.end_sec);
    if (!Number.isFinite(startSec) || !Number.isFinite(endSec) || endSec <= startSec || startSec >= displayDurationSec) {
      return;
    }

    const overlapsSpeech = speechIntervals.some((speech) => startSec < speech.endSec && endSec > speech.startSec);
    if (overlapsSpeech) return;

    const clippedEndSec = Math.min(endSec, displayDurationSec);
    const block = document.createElement("div");
    block.className = "multimodal-timeline-text-block multimodal-timeline-text-block--pause";
    block.style.left = `${Math.max(0, startSec * pxPerSecond)}px`;
    block.style.width = `${Math.max(42, Math.max(0, clippedEndSec - startSec) * pxPerSecond)}px`;
    block.style.top = `0px`;
    block.style.height = `${Math.max(92, trackHeight - 14)}px`;
    block.style.bottom = `0px`;
    block.title = `pause audio · ${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`;

    const blockTitle = document.createElement("strong");
    blockTitle.textContent = "pause audio";
    block.appendChild(blockTitle);

    const blockMeta = document.createElement("span");
    blockMeta.textContent = `${Math.max(0, endSec - startSec).toFixed(2)} s`;
    block.appendChild(blockMeta);

    lane.appendChild(block);
  });
}

function renderAlignmentTimelineLike(container, options = {}) {
  if (!container) return;
  const {
    emptyMessage = "Aucune timeline d’alignement n’est disponible pour le moment.",
    timeline = null,
    motionRows = null,
    requestedView = getSelectedAlignmentImageView(),
    imageTrackViews = null,
    summaryText = "",
    resolveMotionImageSource = (motionRow, view) => resolveAlignmentImageSourceForMotionRow(motionRow, view),
    kickerPrefix = "Alignement",
    showAudioTrack = Boolean(multimodalAlignOverlayAudio?.checked),
    showPauseTrack = Boolean(multimodalAlignOverlayAudio?.checked),
    timelineScaleOverride = null,
    curveModeOverride = "",
    timelineDurationOverride = null,
  } = options;
  clearContainer(container);

  const timelineData = timeline || {};
  const tracks = timelineData?.tracks || {};
  const imageItems = Array.isArray(tracks.images) ? tracks.images : [];
  const textItems = Array.isArray(tracks.text) ? tracks.text : [];
  const pauseItems = Array.isArray(tracks.pauses) ? tracks.pauses : [];
  const audioItems = Array.isArray(tracks.audio_anomalies) ? tracks.audio_anomalies : [];
  const speechRateItems = Array.isArray(tracks.speech_rate) ? tracks.speech_rate : [];
  const motionItems = Array.isArray(tracks.motion_mean) ? tracks.motion_mean : [];
  const entropyItems = Array.isArray(tracks.directional_entropy) ? tracks.directional_entropy : [];

  if (!imageItems.length && !textItems.length && !pauseItems.length && !audioItems.length && !speechRateItems.length && !motionItems.length && !entropyItems.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const effectiveMotionRows = Array.isArray(motionRows) ? motionRows : [];
  const pxPerSecond = Number.isFinite(Number(timelineScaleOverride))
    ? Math.max(60, Math.min(220, Number(timelineScaleOverride)))
    : getSelectedAlignmentTimelineScale();
  const requestedImageViews = Array.isArray(imageTrackViews) && imageTrackViews.length
    ? imageTrackViews
    : [requestedView];
  const imageTrackVisibility = requestedImageViews.map((view) => {
    const renderableItems = imageItems.filter((item) => {
      const motionRow = item?.row || effectiveMotionRows.find((row) => Number(row?.frame_index) === Number(item?.frame_index));
      if (!motionRow) return false;
      const resolvedImage = resolveMotionImageSource(motionRow, view);
      return Boolean(resolvedImage?.src);
    });
    const firstTimeSec = renderableItems.length
      ? Math.min(...renderableItems.map((item) => Number(item?.time_sec) || 0))
      : Number.NaN;
    const lastTimeSec = renderableItems.length
      ? Math.max(...renderableItems.map((item) => Number(item?.time_sec) || 0))
      : Number.NaN;
    return {
      view,
      renderableItems,
      firstTimeSec,
      lastTimeSec,
    };
  });
  const renderableImageEndSecs = imageTrackVisibility
    .map((entry) => Number(entry?.lastTimeSec))
    .filter((value) => Number.isFinite(value) && value > 0);
  const renderableImageStartSecs = imageTrackVisibility
    .map((entry) => Number(entry?.firstTimeSec))
    .filter((value) => Number.isFinite(value) && value >= 0);
  const renderedImageTimes = imageTrackVisibility
    .flatMap((entry) => Array.isArray(entry?.renderableItems) ? entry.renderableItems : [])
    .map((item) => Number(item?.time_sec))
    .filter((value) => Number.isFinite(value) && value >= 0);
  const firstRenderedImageTimeSec = renderedImageTimes.length
    ? Math.min(...renderedImageTimes)
    : Number.NaN;
  const lastRenderedImageTimeSec = renderedImageTimes.length
    ? Math.max(...renderedImageTimes)
    : Number.NaN;
  const lastImageTimeSec = Number.isFinite(lastRenderedImageTimeSec) && lastRenderedImageTimeSec > 0
    ? lastRenderedImageTimeSec
    : (imageItems.length ? Math.max(...imageItems.map((item) => Number(item?.time_sec) || 0)) : 0);
  const computedDurationSec = lastImageTimeSec > 0
    ? Math.max(1, lastImageTimeSec)
    : Math.max(
      1,
      Number(timelineData?.duration_sec || 0),
      ...textItems.map((item) => Number(item?.end_sec) || 0),
      ...pauseItems.map((item) => Number(item?.end_sec) || 0),
      ...audioItems.map((item) => Number(item?.end_sec) || 0),
    );
  const durationSec = Number.isFinite(Number(timelineDurationOverride)) && Number(timelineDurationOverride) > 0
    ? Number(timelineDurationOverride)
    : computedDurationSec;
  const firstVisibleImageTimeSec = Number.isFinite(firstRenderedImageTimeSec)
    ? firstRenderedImageTimeSec
    : (renderableImageStartSecs.length ? Math.min(...renderableImageStartSecs) : Number.NaN);
  const lastVisibleImageTimeSec = Number.isFinite(lastRenderedImageTimeSec)
    ? lastRenderedImageTimeSec
    : (renderableImageEndSecs.length ? Math.max(...renderableImageEndSecs) : Number.NaN);
  const imageThumbWidthPx = 60;
  const imageThumbHalfWidthPx = imageThumbWidthPx / 2;
  const displayDurationSec = Number.isFinite(lastVisibleImageTimeSec) && lastVisibleImageTimeSec > 0
    ? lastVisibleImageTimeSec
    : durationSec;
  const surfaceWidth = Math.ceil((displayDurationSec * pxPerSecond) + imageThumbHalfWidthPx + 8);
  const rulerHeightPx = 34;
  const imageTrackConfigs = requestedImageViews.map((view) => {
    const config = getAlignmentImageViewConfig(view);
    return {
      key: `images__${view}`,
      baseKey: "images",
      view,
      label: config.label,
      hint: "images synchronisées",
      height: 112,
      visible: Boolean(multimodalAlignOverlayImages?.checked) && imageItems.length > 0,
    };
  });

  const trackConfigs = [
    ...imageTrackConfigs,
    {
      key: "text",
      label: "Texte",
      hint: "segments horodatés",
      height: 132,
      visible: Boolean(multimodalAlignOverlaySegments?.checked) && textItems.length > 0,
    },
    {
      key: "pauses",
      label: "Pauses audio",
      hint: "pauses détectées",
      height: 42,
      visible: showPauseTrack && pauseItems.length > 0,
    },
    {
      key: "audio",
      label: "Audio",
      hint: "anomalies",
      height: 42,
      visible: showAudioTrack && audioItems.length > 0,
    },
    {
      key: "speech_rate",
      label: "Débit de parole",
      hint: "mots / seconde",
      height: 64,
      visible: speechRateItems.length > 0,
    },
    {
      key: "motion",
      label: "Mouvement",
      hint: "moyenne",
      height: 64,
      visible: motionItems.length > 0,
    },
    {
      key: "entropy",
      label: "Entropie",
      hint: "directionnelle",
      height: 64,
      visible: entropyItems.length > 0,
    },
  ].filter((track) => track.visible);

  if (!trackConfigs.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "multimodal-timeline";

  const summary = document.createElement("p");
  summary.className = "field-help";
  summary.textContent = summaryText
    || `Timeline multimodale · ${displayDurationSec.toFixed(2)} s · ${imageItems.length} image(s) · ${textItems.length} segment(s).`;
  wrapper.appendChild(summary);

  const shell = document.createElement("div");
  shell.className = "multimodal-timeline-shell";

  const labels = document.createElement("div");
  labels.className = "multimodal-timeline-labels";

  const scroll = document.createElement("div");
  scroll.className = "multimodal-timeline-scroll";

  const surfaces = document.createElement("div");
  surfaces.className = "multimodal-timeline-surfaces";
  surfaces.style.width = `${surfaceWidth}px`;

  const rulerLabel = document.createElement("div");
  rulerLabel.className = "multimodal-timeline-label multimodal-timeline-label--ruler";
  rulerLabel.textContent = "Temps";
  rulerLabel.style.height = `${rulerHeightPx}px`;
  labels.appendChild(rulerLabel);

  const ruler = document.createElement("div");
  ruler.className = "multimodal-timeline-ruler";
  ruler.style.height = `${rulerHeightPx}px`;
  ruler.style.width = `${surfaceWidth}px`;
  for (let second = 0; second <= Math.ceil(displayDurationSec); second += 1) {
    const tick = document.createElement("div");
    tick.className = "multimodal-timeline-tick";
    tick.style.left = `${second * pxPerSecond}px`;
    const text = document.createElement("span");
    text.textContent = `${second}s`;
    tick.appendChild(text);
    ruler.appendChild(tick);
  }
  surfaces.appendChild(ruler);

  const curveMode = String(curveModeOverride || "").trim().toLowerCase() === "raw"
    ? "raw"
    : String(curveModeOverride || "").trim().toLowerCase() === "smooth"
      ? "smooth"
      : getSelectedAlignmentCurveMode();

  const buildCurvePath = (points, smoothed) => {
    if (!points.length) return "";
    if (points.length === 1) {
      return `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
    }
    if (!smoothed) {
      return points.map((point, index) =>
        `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`
      ).join(" ");
    }
    let path = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
    for (let index = 1; index < points.length - 1; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      const midX = (current.x + next.x) / 2;
      const midY = (current.y + next.y) / 2;
      path += ` Q ${current.x.toFixed(2)} ${current.y.toFixed(2)} ${midX.toFixed(2)} ${midY.toFixed(2)}`;
    }
    const beforeLast = points[points.length - 2];
    const last = points[points.length - 1];
    path += ` Q ${beforeLast.x.toFixed(2)} ${beforeLast.y.toFixed(2)} ${last.x.toFixed(2)} ${last.y.toFixed(2)}`;
    return path;
  };

  const renderValueTrack = (lane, items, valueKey, trackKey) => {
    const chartHeight = Math.max(36, (Number.parseFloat(lane.style.height) || 80) - 8);
    const padX = 10;
    const padTop = 10;
    const padBottom = 12;
    const usableWidth = Math.max(24, surfaceWidth - (padX * 2));
    const usableHeight = Math.max(20, chartHeight - padTop - padBottom);
    const points = items
      .map((item) => {
        const rawTimeSec = Number(item?.time_sec);
        const value = Number(item?.[valueKey] ?? item?.value);
        if (!Number.isFinite(rawTimeSec) || !Number.isFinite(value)) return null;
        if (Number.isFinite(firstVisibleImageTimeSec) && rawTimeSec < firstVisibleImageTimeSec) return null;
        if (Number.isFinite(lastVisibleImageTimeSec) && rawTimeSec > lastVisibleImageTimeSec) return null;
        const timeSec = Math.max(0, Math.min(displayDurationSec, rawTimeSec));
        return {
          x: padX + ((Math.max(0, timeSec) / Math.max(displayDurationSec, 0.000001)) * usableWidth),
          value,
          timeSec,
          frameIndex: Number(item?.frame_index),
          label: String(item?.label || ""),
        };
      })
      .filter(Boolean);

    if (!points.length) return;

    const values = points.map((point) => point.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const range = Math.max(0.000001, maxValue - minValue);
    points.forEach((point) => {
      point.y = padTop + usableHeight - (((point.value - minValue) / range) * usableHeight);
      if (range <= 0.000001) {
        point.y = padTop + (usableHeight / 2);
      }
    });

    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", `multimodal-timeline-chart-svg multimodal-timeline-chart-svg--${trackKey}`);
    svg.setAttribute("viewBox", `0 0 ${surfaceWidth} ${chartHeight}`);
    svg.setAttribute("preserveAspectRatio", "none");

    const midGuide = document.createElementNS(svgNS, "line");
    midGuide.setAttribute("class", "multimodal-timeline-chart-guide");
    midGuide.setAttribute("x1", "0");
    midGuide.setAttribute("x2", String(surfaceWidth));
    midGuide.setAttribute("y1", String(padTop + (usableHeight / 2)));
    midGuide.setAttribute("y2", String(padTop + (usableHeight / 2)));
    svg.appendChild(midGuide);

    const path = document.createElementNS(svgNS, "path");
    path.setAttribute("class", "multimodal-timeline-chart-path");
    path.setAttribute("d", buildCurvePath(points, curveMode === "smooth"));
    svg.appendChild(path);

    lane.appendChild(svg);
  };

  trackConfigs.forEach((track) => {
    const label = document.createElement("div");
    label.className = "multimodal-timeline-label multimodal-timeline-label--track";
    label.style.height = `${track.height}px`;
    const labelTitle = document.createElement("strong");
    labelTitle.textContent = track.label;
    label.appendChild(labelTitle);
    const labelHint = document.createElement("span");
    labelHint.textContent = track.hint;
    label.appendChild(labelHint);
    labels.appendChild(label);

    const lane = document.createElement("div");
    lane.className = `multimodal-timeline-lane multimodal-timeline-lane--${track.key}`;
    lane.style.height = `${track.height}px`;

    if (track.baseKey === "images" || String(track.key || "").startsWith("images__")) {
      const currentView = String(track.view || requestedView || "brute").trim() || "brute";
      imageItems.forEach((item, index) => {
        const itemTimeSec = Number(item?.time_sec);
        if (Number.isFinite(lastVisibleImageTimeSec) && itemTimeSec > lastVisibleImageTimeSec) return;
        if (Number.isFinite(itemTimeSec) && itemTimeSec > displayDurationSec) return;
        const motionRow = item?.row || effectiveMotionRows.find((row) => Number(row?.frame_index) === Number(item?.frame_index));
        if (!motionRow) return;
        const resolvedImage = resolveMotionImageSource(motionRow, currentView);
        if (!resolvedImage.src) return;
        const figure = document.createElement("figure");
        figure.className = "multimodal-timeline-image-item";
        const centeredLeftPx = (Number(item?.time_sec) * pxPerSecond) - imageThumbHalfWidthPx;
        figure.style.left = `${Math.max(0, Math.min(surfaceWidth - imageThumbWidthPx, centeredLeftPx))}px`;
        figure.appendChild(
          createPreviewableImage({
            src: resolvedImage.src,
            alt: `Image ${index + 1}`,
            title: Number.isFinite(item?.frame_index) ? `Image ${item.frame_index}` : `Image ${index + 1}`,
            kicker: `${kickerPrefix} · ${resolvedImage.label}`,
          })
        );
        const figcaption = document.createElement("figcaption");
        figcaption.textContent = Number.isFinite(item?.time_sec)
          ? `${Number(item.time_sec).toFixed(2)} s`
          : resolvedImage.label;
        figure.appendChild(figcaption);
        lane.appendChild(figure);
      });
    } else if (track.key === "text") {
      textItems.forEach((item, index) => {
        const layout = resolveTextTrackPauseLayout(item, pauseItems, displayDurationSec);
        if (!layout || layout.laneStartSec >= displayDurationSec) return;
        const group = document.createElement("div");
        group.className = "multimodal-timeline-text-group";
        const clippedLaneEndSec = Math.min(layout.laneEndSec, displayDurationSec);
        const groupWidth = Math.max(32, Math.max(0, clippedLaneEndSec - layout.laneStartSec) * pxPerSecond);
        group.style.left = `${Math.max(0, layout.laneStartSec * pxPerSecond)}px`;
        group.style.width = `${groupWidth}px`;
        group.style.height = `${Math.max(92, track.height - 14)}px`;

        const speechBlock = document.createElement("div");
        speechBlock.className = "multimodal-timeline-text-block multimodal-timeline-text-block--speech";
        const speechStartSec = Number(item?.start_sec);
        const speechEndSec = Number(item?.end_sec);
        const startSec = layout.speechStartSec;
        const endSec = layout.speechEndSec;
        const clippedEndSec = Math.min(endSec, displayDurationSec);
        const speechDurationSec = Number(item?.speech_duration_sec);
        const contextDurationSec = Number(item?.context_duration_sec);
        const speechLeftPx = Math.max(0, (startSec - layout.laneStartSec) * pxPerSecond);
        const speechWidthPx = Math.max(32, Math.max(0, clippedEndSec - startSec) * pxPerSecond);
        speechBlock.style.left = `${speechLeftPx}px`;
        speechBlock.style.width = `${speechWidthPx}px`;
        speechBlock.style.top = `0px`;
        speechBlock.style.bottom = `0px`;
        const tooltipParts = [`parole ${speechStartSec.toFixed(2)} s → ${speechEndSec.toFixed(2)} s`];
        if (Number.isFinite(startSec) && Number.isFinite(endSec) && (Math.abs(startSec - speechStartSec) > 0.001 || Math.abs(endSec - speechEndSec) > 0.001)) {
          tooltipParts.push(`images ${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`);
        }
        if (Number.isFinite(contextDurationSec) && contextDurationSec > 0) {
          tooltipParts.push(`total ${contextDurationSec.toFixed(2)} s`);
        } else if (Number.isFinite(speechDurationSec) && speechDurationSec > 0) {
          tooltipParts.push(`durée ${speechDurationSec.toFixed(2)} s`);
        }
        tooltipParts.push(String(item?.text || "").trim());
        speechBlock.title = tooltipParts.join(" · ");
        const blockTitle = document.createElement("strong");
        blockTitle.textContent = item.segment_id ? `Segment ${item.segment_id}` : `Segment ${index + 1}`;
        speechBlock.appendChild(blockTitle);
        const timedSlots = createAlignmentTimedTextSlots(item, layout, imageItems, pxPerSecond);
        speechBlock.appendChild(timedSlots || createAlignmentReadableTextLine(item, layout, null));

        group.appendChild(speechBlock);
        lane.appendChild(group);
      });
      renderStandalonePausesInTextLane(lane, pauseItems, textItems, pxPerSecond, displayDurationSec, track.height);
    } else if (track.key === "pauses") {
      mergePauseSegmentsForDisplay(
        pauseItems.map((item) => ({
          ...item,
          startSec: Number(item?.start_sec),
          endSec: Number(item?.end_sec),
        }))
      ).forEach((item) => {
        const startSec = Number(item?.startSec ?? item?.start_sec);
        const endSec = Number(item?.endSec ?? item?.end_sec);
        if (!Number.isFinite(startSec) || !Number.isFinite(endSec) || startSec >= displayDurationSec) return;
        const clippedEndSec = Math.min(endSec, displayDurationSec);
        const block = document.createElement("div");
        block.className = "multimodal-timeline-audio-block";
        block.style.left = `${Math.max(0, startSec * pxPerSecond)}px`;
        block.style.width = `${Math.max(10, Math.max(0, clippedEndSec - startSec) * pxPerSecond)}px`;
        block.style.background = "linear-gradient(90deg, #6d7b88, #9aa7b2)";
        const pauseDurationSec = Math.max(0, endSec - startSec);
        const pauseKindLabel = "pause audio";
        block.title = `${pauseKindLabel} · ${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`;
        const blockTitle = document.createElement("strong");
        blockTitle.textContent = pauseKindLabel;
        block.appendChild(blockTitle);
        const blockMeta = document.createElement("span");
        blockMeta.textContent = Number.isFinite(pauseDurationSec)
          ? `${pauseDurationSec.toFixed(2)} s`
          : `${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`;
        block.appendChild(blockMeta);
        lane.appendChild(block);
      });
    } else if (track.key === "audio") {
      audioItems.forEach((item) => {
        const startSec = Number(item?.start_sec);
        const endSec = Number(item?.end_sec);
        if (!Number.isFinite(startSec) || !Number.isFinite(endSec) || startSec >= displayDurationSec) return;
        const clippedEndSec = Math.min(endSec, displayDurationSec);
        const block = document.createElement("div");
        block.className = "multimodal-timeline-audio-block";
        block.style.left = `${Math.max(0, startSec * pxPerSecond)}px`;
        block.style.width = `${Math.max(10, Math.max(0, clippedEndSec - startSec) * pxPerSecond)}px`;
        const zScore = Number(item?.z_score);
        block.title = Number.isFinite(zScore)
          ? `Anomalie audio · ${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s · z-score ${zScore.toFixed(3)}`
          : `Anomalie audio · ${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`;
        const blockTitle = document.createElement("strong");
        blockTitle.textContent = "anomalie audio";
        block.appendChild(blockTitle);
        const blockMeta = document.createElement("span");
        blockMeta.textContent = Number.isFinite(zScore)
          ? `z-score ${zScore.toFixed(2)}`
          : `${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`;
        block.appendChild(blockMeta);
        lane.appendChild(block);
      });
    } else if (track.key === "speech_rate") {
      renderValueTrack(lane, speechRateItems, "value", "speech-rate");
    } else if (track.key === "motion") {
      renderValueTrack(lane, motionItems, "value", "motion");
    } else if (track.key === "entropy") {
      renderValueTrack(lane, entropyItems, "value", "entropy");
    }

    surfaces.appendChild(lane);
  });

  scroll.appendChild(surfaces);
  shell.appendChild(labels);
  shell.appendChild(scroll);
  wrapper.appendChild(shell);
  container.appendChild(wrapper);
}

function renderAlignmentTimeline(container, options = {}) {
  renderAlignmentTimelineLike(container, {
    ...options,
    timeline: getParsedAlignmentTimelineData(),
    motionRows: getParsedMotionRows() || [],
    requestedView: getSelectedAlignmentImageView(),
    resolveMotionImageSource: (motionRow, view) => resolveAlignmentImageSourceForMotionRow(motionRow, view),
    kickerPrefix: "Alignement",
  });
}

function renderAlignmentCards(container, options = {}) {
  if (!container) return;
  const { emptyMessage = "Le fichier d'alignement est vide ou illisible.", maxItems = null } = options;
  clearContainer(container);

  const parsedRows = getParsedAlignmentRows();
  if (!Array.isArray(parsedRows) || !parsedRows.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const gallery = document.createElement("div");
  gallery.className = "multimodal-segment-sync-list";

  const visibleRows = Number.isFinite(maxItems) ? parsedRows.slice(0, maxItems) : parsedRows;
  const requestedView = getSelectedAlignmentImageView();
  const motionRows = getParsedMotionRows();
  visibleRows.forEach((row, index) => {
    const card = document.createElement("article");
    card.className = "multimodal-segment-sync-card";

    const header = document.createElement("div");
    header.className = "multimodal-segment-sync-header";

    const title = document.createElement("h4");
    const segmentId = String(row.segment_id || row.segmentId || "").trim();
    title.textContent = segmentId ? `Segment ${segmentId}` : `Segment ${index + 1}`;
    header.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "multimodal-segment-sync-meta";
    const startSec = Number(row.start_sec);
    const endSec = Number(row.end_sec);
    const frameCount = Number(row.frame_count_sync);
    const timeLabel = Number.isFinite(startSec) && Number.isFinite(endSec)
      ? `${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`
      : "Horodatage indisponible";
    const frameLabel = Number.isFinite(frameCount) ? `${frameCount} image(s)` : "0 image";
    meta.textContent = `${timeLabel} · ${frameLabel}`;
    header.appendChild(meta);
    card.appendChild(header);

    const body = document.createElement("div");
    body.className = "multimodal-segment-sync-body";

    const imageBlock = document.createElement("div");
    imageBlock.className = "multimodal-segment-sync-image";
    const segmentMotionRows = getMotionRowsWithinAlignmentSegment(row, motionRows);
    const segmentGallery = document.createElement("div");
    segmentGallery.className = "multimodal-alignment-segment-gallery";

    if (segmentMotionRows.length) {
      const timelineTitle = document.createElement("p");
      timelineTitle.className = "field-help";
      timelineTitle.textContent = `Timeline du segment : ${segmentMotionRows.length} image(s) dans l'ordre temporel.`;
      imageBlock.appendChild(timelineTitle);

      segmentMotionRows.forEach((motionRow, motionIndex) => {
        const resolvedImage = resolveAlignmentImageSourceForMotionRow(motionRow, requestedView);
        if (!resolvedImage.src) return;

        const item = document.createElement("figure");
        item.className = "multimodal-alignment-segment-gallery-item";
        item.appendChild(
          createPreviewableImage({
            src: resolvedImage.src,
            alt: `${title.textContent} · image ${motionIndex + 1}`,
            title: `${title.textContent} · image ${motionIndex + 1}`,
            kicker: `Alignement · ${resolvedImage.label}`
          })
        );
        const figcaption = document.createElement("figcaption");
        figcaption.className = "result-gallery-caption";
        const timeSec = Number(motionRow?.time_sec);
        const frameIndex = Number(motionRow?.frame_index);
        const parts = [resolvedImage.label];
        if (Number.isFinite(frameIndex)) parts.push(`image ${frameIndex}`);
        if (Number.isFinite(timeSec)) parts.push(`${timeSec.toFixed(2)} s`);
        figcaption.textContent = parts.join(" · ");
        item.appendChild(figcaption);
        if (resolvedImage.fallbackNote) {
          const fallback = document.createElement("p");
          fallback.className = "field-help";
          fallback.textContent = resolvedImage.fallbackNote;
          item.appendChild(fallback);
        }
        item.appendChild(createHighlightedAlignmentText(row, timeSec));
        segmentGallery.appendChild(item);
      });
      imageBlock.appendChild(segmentGallery);
    } else {
      const resolvedImage = resolveAlignmentImageSource(row, requestedView, motionRows);
      if (resolvedImage.src) {
        imageBlock.appendChild(
          createPreviewableImage({
            src: resolvedImage.src,
            alt: title.textContent,
            title: title.textContent,
            kicker: `Alignement · ${resolvedImage.label}`
          })
        );
      } else {
        imageBlock.appendChild(createEmptyState("Aucune image synchronisée disponible pour ce segment."));
      }
      imageBlock.appendChild(createHighlightedAlignmentText(row));
    }

    body.appendChild(imageBlock);

    card.appendChild(body);
    gallery.appendChild(card);
  });

  container.appendChild(gallery);
}

function renderAlignmentImageGroups(container, options = {}) {
  if (!container) return;
  const { emptyMessage = "Le fichier d'alignement est vide ou illisible." } = options;
  clearContainer(container);

  const parsedRows = getParsedAlignmentRows();
  if (!Array.isArray(parsedRows) || !parsedRows.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const requestedView = getSelectedAlignmentImageView();
  const motionRows = getParsedMotionRows();
  const groups = new Map();

  parsedRows.forEach((row, index) => {
    const resolvedImage = resolveAlignmentImageSource(row, requestedView, motionRows);
    const fallbackKey = getAlignmentFramePathCandidates(row).join("|") || `segment-${index + 1}`;
    const groupKey = resolvedImage.absolutePath || fallbackKey;
    if (!groups.has(groupKey)) {
      groups.set(groupKey, {
        resolvedImage,
        rows: [],
        sortTime: Number(row?.nearest_frame_time_sec_sync),
      });
    }
    groups.get(groupKey).rows.push(row);
  });

  const orderedGroups = Array.from(groups.values()).sort((left, right) => {
    const leftTime = Number.isFinite(left.sortTime) ? left.sortTime : Number.POSITIVE_INFINITY;
    const rightTime = Number.isFinite(right.sortTime) ? right.sortTime : Number.POSITIVE_INFINITY;
    return leftTime - rightTime;
  });

  if (!orderedGroups.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const gallery = document.createElement("div");
  gallery.className = "multimodal-segment-sync-list";

  orderedGroups.forEach((group, index) => {
    const card = document.createElement("article");
    card.className = "multimodal-segment-sync-card";

    const header = document.createElement("div");
    header.className = "multimodal-segment-sync-header";

    const title = document.createElement("h4");
    title.textContent = `Image ${index + 1}`;
    header.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "multimodal-segment-sync-meta";
    meta.textContent = `${group.rows.length} segment(s) synchronisé(s)`;
    header.appendChild(meta);
    card.appendChild(header);

    const body = document.createElement("div");
    body.className = "multimodal-segment-sync-body";

    const imageBlock = document.createElement("div");
    imageBlock.className = "multimodal-segment-sync-image";

    if (group.resolvedImage.src) {
      imageBlock.appendChild(
        createPreviewableImage({
          src: group.resolvedImage.src,
          alt: title.textContent,
          title: title.textContent,
          kicker: `Alignement · ${group.resolvedImage.label}`
        })
      );

      const caption = document.createElement("p");
      caption.className = "result-gallery-caption";
      const groupTime = Number(group.sortTime);
      const captionParts = [group.resolvedImage.label];
      if (Number.isFinite(groupTime)) {
        captionParts.push(`temps image : ${groupTime.toFixed(2)} s`);
      }
      caption.textContent = captionParts.join(" · ");
      imageBlock.appendChild(caption);

      if (group.resolvedImage.fallbackNote) {
        const fallback = document.createElement("p");
        fallback.className = "field-help";
        fallback.textContent = group.resolvedImage.fallbackNote;
        imageBlock.appendChild(fallback);
      }

      const textList = document.createElement("div");
      textList.className = "multimodal-segment-sync-text-list";

      group.rows.forEach((row) => {
        const entry = document.createElement("div");
        entry.className = "multimodal-segment-sync-text-entry";

        const entryMeta = document.createElement("p");
        entryMeta.className = "multimodal-segment-sync-meta";
        const startSec = Number(row?.start_sec);
        const endSec = Number(row?.end_sec);
        entryMeta.textContent = Number.isFinite(startSec) && Number.isFinite(endSec)
          ? `${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`
          : "Horodatage indisponible";
        entry.appendChild(entryMeta);

        entry.appendChild(createHighlightedAlignmentText(row));

        textList.appendChild(entry);
      });

      imageBlock.appendChild(textList);
    } else {
      imageBlock.appendChild(createEmptyState("Aucune image synchronisée disponible pour cette vue."));
    }

    body.appendChild(imageBlock);
    card.appendChild(body);
    gallery.appendChild(card);
  });

  container.appendChild(gallery);
}

function renderMultimodalAlignmentResults() {
  renderAlignmentTimeline(multimodalAlignPreview, {
    emptyMessage: "Aucune timeline d'alignement n'est disponible pour le moment. Importe un CSV de segments et garde une séquence d'images analysée disponible.",
  });
}

function parseMultimodalNodesGraphPayload() {
  const result = appState.multimodalResults?.noeuds;
  const artifact = result?.graphJsonArtifact || null;
  if (!artifact) return null;
  try {
    return JSON.parse(artifactDataToText(artifact));
  } catch (_error) {
    return null;
  }
}

function formatNodeTimeLabel(node) {
  const startSec = Number(node?.start_sec);
  const endSec = Number(node?.end_sec);
  const timeSec = Number(node?.time_sec);
  if (Number.isFinite(startSec) && Number.isFinite(endSec) && endSec > startSec) {
    return `${startSec.toFixed(2)} s → ${endSec.toFixed(2)} s`;
  }
  if (Number.isFinite(timeSec)) {
    return `${timeSec.toFixed(2)} s`;
  }
  return "N/A";
}

function renderMultimodalNodesSummaryResult(container, payload) {
  clearContainer(container);
  const summary = payload?.summary || {};
  const selectionMode = String(summary?.selection_mode || "threshold");
  const cards = [
    ["Événements visuels", summary?.event_count],
    ["Segments texte", summary?.text_node_count],
    ["Liens", summary?.edge_count],
    ["Entropie max", summary?.max_entropy_peak],
    ["Mode", selectionMode === "local-peaks" ? "Pics locaux" : "Moyenne + kσ"],
  ];
  if (selectionMode !== "local-peaks") {
    cards.push(["Seuil entropie", summary?.entropy_threshold]);
  }
  const grid = document.createElement("div");
  grid.className = "comparison-ab-summary-grid";
  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "comparison-ab-summary-card";
    const title = document.createElement("strong");
    title.textContent = String(label);
    const content = document.createElement("span");
    content.textContent = formatSummaryValue(value);
    card.append(title, content);
    grid.appendChild(card);
  });
  container.appendChild(grid);
  if (selectionMode === "local-peaks") {
    const note = document.createElement("p");
    note.className = "field-help";
    note.textContent = "Mode actif : pics locaux. Le graphe retient les sommets d'entropie par rapport à leurs voisines, puis regroupe les images consécutives.";
    container.appendChild(note);
  } else if (Number.isFinite(Number(summary?.mean_entropy_global)) && Number.isFinite(Number(summary?.std_entropy_global))) {
    const note = document.createElement("p");
    note.className = "field-help";
    note.textContent = `Sélection des événements : H ≥ μ + kσ, avec μ = ${Number(summary.mean_entropy_global).toFixed(3)}, σ = ${Number(summary.std_entropy_global).toFixed(3)}, k = ${Number(summary?.entropy_k ?? 1).toFixed(1)}.`;
    container.appendChild(note);
  }
}

function syncMultimodalNodesControls() {
  if (!multimodalNodesEntropyK) return;
  const eventMode = String(multimodalNodesEventMode?.value || "threshold");
  multimodalNodesEntropyK.disabled = eventMode === "local-peaks";
}

function renderMultimodalNodeDetail(container, payload, nodeId) {
  clearContainer(container);
  const nodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
  const edges = Array.isArray(payload?.edges) ? payload.edges : [];
  const motionResult = appState.multimodalResults?.mouvements || null;
  const node = nodes.find((entry) => String(entry?.id) === String(nodeId)) || nodes[0] || null;
  if (!node) {
    container.appendChild(createEmptyState("Aucun nœud sélectionné."));
    return;
  }

  const title = document.createElement("h4");
  title.textContent = String(node?.label || "Nœud");
  container.appendChild(title);

  const meta = document.createElement("p");
  meta.className = "field-help";
  meta.textContent = `${node?.type === "event" ? "Événement visuel" : "Segment texte"} · ${formatNodeTimeLabel(node)}`;
  container.appendChild(meta);

  if (node?.type === "event") {
    const stablePreviewPaths = uniqueNonEmptyStrings([
      node?.entropy_preview_path,
      node?.frame_preview_path,
    ]);
    const previewPaths = stablePreviewPaths.length
      ? stablePreviewPaths
      : uniqueNonEmptyStrings([node?.image_path]);
    const previewUrls = previewPaths
      .map((path) => {
        const artifact = motionResult
          ? findArtifactForAbsolutePath(motionResult.artifacts, motionResult.outputDir, path)
          : null;
        return artifact ? artifactDataToObjectUrl(artifact) : maybeCreateLocalFileUrl(path);
      })
      .filter(Boolean);
    if (previewUrls.length) {
      const previewImage = createPreviewableImage({
        src: previewUrls[0],
        alt: String(node?.label || "Événement visuel"),
        title: String(node?.label || "Événement visuel"),
        kicker: "Noeuds"
      });
      let previewIndex = 0;
      previewImage.addEventListener("error", () => {
        previewIndex += 1;
        if (previewIndex < previewUrls.length) {
          previewImage.src = previewUrls[previewIndex];
        }
      }, { once: false });
      container.appendChild(previewImage);
    } else {
      container.appendChild(createEmptyState("Image d'événement introuvable."));
    }
    const list = document.createElement("dl");
    list.className = "motion-metrics-list";
    [
      ["Entropie pic", Number(node?.entropy_peak)],
      ["Entropie moyenne", Number(node?.entropy_mean)],
      ["Mouvement moyen", Number(node?.motion_mean)],
      ["Direction", String(node?.direction_label || "").trim()],
    ].forEach(([label, rawValue]) => {
      if (rawValue === "" || rawValue === null || rawValue === undefined) return;
      const dt = document.createElement("dt");
      dt.textContent = String(label);
      const dd = document.createElement("dd");
      dd.textContent = typeof rawValue === "number" && Number.isFinite(rawValue)
        ? rawValue.toFixed(3)
        : String(rawValue);
      list.append(dt, dd);
    });
    container.appendChild(list);
  } else {
    const text = document.createElement("p");
    text.className = "lda-segment-text";
    text.textContent = String(node?.text || node?.text_excerpt || "").trim() || "Aucun texte.";
    container.appendChild(text);
  }

  const linkedEdges = edges.filter((edge) => String(edge?.source) === String(node.id) || String(edge?.target) === String(node.id));
  if (linkedEdges.length) {
    const related = document.createElement("div");
    related.className = "result-table-caption";
    related.textContent = `${linkedEdges.length} lien(s) associé(s).`;
    container.appendChild(related);
  }
}

function buildMultimodalNodesNetworkLayout(nodes, edges, width, height) {
  const margin = 64;
  const innerWidth = Math.max(240, width - (margin * 2));
  const innerHeight = Math.max(240, height - (margin * 2));
  const events = nodes.filter((node) => node?.type === "event");
  const texts = nodes.filter((node) => node?.type === "text");
  const degreeById = new Map();
  edges.forEach((edge) => {
    const sourceId = String(edge?.source || "");
    const targetId = String(edge?.target || "");
    if (sourceId) degreeById.set(sourceId, (degreeById.get(sourceId) || 0) + 1);
    if (targetId) degreeById.set(targetId, (degreeById.get(targetId) || 0) + 1);
  });

  const positionedNodes = nodes.map((node, index) => {
    const isEvent = node?.type === "event";
    const bucket = isEvent ? events : texts;
    const bucketIndex = Math.max(0, bucket.findIndex((entry) => String(entry?.id) === String(node?.id)));
    const count = Math.max(1, bucket.length);
    const ratio = count === 1 ? 0.5 : bucketIndex / (count - 1);
    const baseX = isEvent
      ? margin + (innerWidth * 0.28)
      : margin + (innerWidth * 0.72);
    const wave = Math.sin((ratio * Math.PI * 2) + (isEvent ? 0 : Math.PI / 3)) * Math.min(90, innerWidth * 0.12);
    const baseY = margin + (innerHeight * (0.12 + (ratio * 0.76)));
    return {
      ...node,
      x: baseX + wave,
      y: baseY,
      vx: 0,
      vy: 0,
      radius: isEvent ? 18 : 16,
      degree: degreeById.get(String(node?.id)) || 0,
      clusterX: baseX,
    };
  });

  const nodeById = new Map(positionedNodes.map((node) => [String(node.id), node]));
  const springs = edges
    .map((edge) => {
      const source = nodeById.get(String(edge?.source || ""));
      const target = nodeById.get(String(edge?.target || ""));
      if (!source || !target) return null;
      const isCrossType = source.type !== target.type;
      return {
        source,
        target,
        restLength: isCrossType ? 220 : 140,
        strength: isCrossType ? 0.022 : 0.014,
      };
    })
    .filter(Boolean);

  for (let iteration = 0; iteration < 180; iteration += 1) {
    for (let leftIndex = 0; leftIndex < positionedNodes.length; leftIndex += 1) {
      const left = positionedNodes[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < positionedNodes.length; rightIndex += 1) {
        const right = positionedNodes[rightIndex];
        let dx = right.x - left.x;
        let dy = right.y - left.y;
        let distanceSq = (dx * dx) + (dy * dy);
        if (distanceSq < 1) {
          dx = 0.5 - Math.random();
          dy = 0.5 - Math.random();
          distanceSq = (dx * dx) + (dy * dy);
        }
        const distance = Math.sqrt(distanceSq);
        const force = Math.min(3600, 1900 / distanceSq);
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        left.vx -= fx;
        left.vy -= fy;
        right.vx += fx;
        right.vy += fy;
      }
    }

    springs.forEach((spring) => {
      const dx = spring.target.x - spring.source.x;
      const dy = spring.target.y - spring.source.y;
      const distance = Math.max(1, Math.sqrt((dx * dx) + (dy * dy)));
      const delta = distance - spring.restLength;
      const force = delta * spring.strength;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;
      spring.source.vx += fx;
      spring.source.vy += fy;
      spring.target.vx -= fx;
      spring.target.vy -= fy;
    });

    positionedNodes.forEach((node) => {
      const pullX = (node.clusterX - node.x) * 0.008;
      const pullY = ((height / 2) - node.y) * 0.0015;
      node.vx += pullX;
      node.vy += pullY;
      node.vx *= 0.79;
      node.vy *= 0.79;
      node.x += node.vx;
      node.y += node.vy;
      node.x = Math.max(margin, Math.min(width - margin, node.x));
      node.y = Math.max(margin, Math.min(height - margin, node.y));
    });
  }

  return positionedNodes;
}

function renderMultimodalNodesGraphResult(container, detailContainer, payload) {
  clearContainer(container);
  const nodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
  const edges = Array.isArray(payload?.edges) ? payload.edges : [];
  if (!nodes.length) {
    container.appendChild(createEmptyState("Aucun nœud n'a été calculé."));
    clearContainer(detailContainer);
    detailContainer.appendChild(createEmptyState("Aucun détail à afficher."));
    return;
  }

  const width = Math.max(980, Math.min(1560, 920 + (nodes.length * 26)));
  const height = Math.max(520, Math.min(920, 420 + (nodes.length * 18)));
  const positionedNodes = buildMultimodalNodesNetworkLayout(nodes, edges, width, height);
  const nodeById = new Map(positionedNodes.map((node) => [String(node.id), node]));

  const wrapper = document.createElement("div");
  wrapper.className = "multimodal-nodes-graph-wrap";
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("class", "multimodal-nodes-graph");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const leftLabel = document.createElementNS(svgNS, "text");
  leftLabel.setAttribute("x", "46");
  leftLabel.setAttribute("y", "34");
  leftLabel.setAttribute("class", "multimodal-nodes-zone-label");
  leftLabel.textContent = "Événements visuels";
  svg.appendChild(leftLabel);

  const rightLabel = document.createElementNS(svgNS, "text");
  rightLabel.setAttribute("x", String(width - 210));
  rightLabel.setAttribute("y", "34");
  rightLabel.setAttribute("class", "multimodal-nodes-zone-label");
  rightLabel.textContent = "Segments texte liés";
  svg.appendChild(rightLabel);

  edges.forEach((edge) => {
    const source = nodeById.get(String(edge?.source));
    const target = nodeById.get(String(edge?.target));
    if (!source || !target) return;
    const path = document.createElementNS(svgNS, "path");
    const controlX = (source.x + target.x) / 2;
    const verticalLift = source.type === target.type ? 28 : 0;
    const controlY = ((source.y + target.y) / 2) - verticalLift;
    path.setAttribute("d", `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`);
    path.setAttribute("class", `multimodal-nodes-edge multimodal-nodes-edge--${String(edge?.type || "temporal")}`);
    svg.appendChild(path);
  });

  positionedNodes.forEach((node) => {
    const circle = document.createElementNS(svgNS, "circle");
    circle.setAttribute("cx", String(node.x));
    circle.setAttribute("cy", String(node.y));
    circle.setAttribute("r", String(node.radius + Math.min(6, node.degree)));
    circle.setAttribute("class", `multimodal-nodes-node multimodal-nodes-node--${node.type === "event" ? "event" : "text"}`);
    circle.style.cursor = "pointer";
    circle.addEventListener("click", () => renderMultimodalNodeDetail(detailContainer, payload, node.id));
    svg.appendChild(circle);

    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", String(node.x));
    label.setAttribute("y", String(node.y + 4));
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "multimodal-nodes-node-label");
    label.textContent = node.type === "event"
      ? `E${String(node.id).replace("event_", "")}`
      : `S${String(node.segment_id || node.id).replace("text_", "")}`;
    label.setAttribute("fill", node.type === "event" ? "#ffffff" : "#5a4838");
    label.style.cursor = "pointer";
    label.addEventListener("click", () => renderMultimodalNodeDetail(detailContainer, payload, node.id));
    svg.appendChild(label);

    const caption = document.createElementNS(svgNS, "text");
    caption.setAttribute("x", String(node.x));
    caption.setAttribute("y", String(node.y + node.radius + 18));
    caption.setAttribute("text-anchor", "middle");
    caption.setAttribute("class", "multimodal-nodes-node-caption");
    caption.textContent = node.type === "event"
      ? formatNodeTimeLabel(node)
      : String(node?.label || "");
    svg.appendChild(caption);
  });

  wrapper.appendChild(svg);
  container.appendChild(wrapper);
  renderMultimodalNodeDetail(detailContainer, payload, positionedNodes[0]?.id);
}

function renderMultimodalNodesResults() {
  syncMultimodalNodesControls();
  const result = appState.multimodalResults?.noeuds;
  const payload = parseMultimodalNodesGraphPayload();
  const nodesRequestReady = Boolean(buildMultimodalNodesArgs());

  if (multimodalNodesSourcesStatus) {
    if (result?.outputDir) {
      setReadonlyStatus(multimodalNodesSourcesStatus, `Graphe disponible : ${result.outputDir}`);
    } else if (!nodesRequestReady) {
      setReadonlyStatus(multimodalNodesSourcesStatus, "Lance d'abord l'alignement et garde les mouvements disponibles pour construire les nœuds.");
    } else {
      setReadonlyStatus(multimodalNodesSourcesStatus, "Les sources sont prêtes. Tu peux construire le graphe de nœuds.");
    }
  }

  if (!payload) {
    clearContainer(multimodalNodesSummary);
    clearContainer(multimodalNodesGraph);
    clearContainer(multimodalNodesDetail);
    clearContainer(multimodalNodesTable);
    clearContainer(multimodalEdgesTable);
    multimodalNodesSummary?.appendChild(createEmptyState("Aucun résumé de nœuds n'est disponible."));
    multimodalNodesGraph?.appendChild(createEmptyState("Aucun graphe de nœuds n'est disponible."));
    multimodalNodesDetail?.appendChild(createEmptyState("Aucun détail à afficher."));
    multimodalNodesTable?.appendChild(createEmptyState("Aucun tableau de nœuds n'est disponible."));
    multimodalEdgesTable?.appendChild(createEmptyState("Aucun tableau de liens n'est disponible."));
    return;
  }

  renderMultimodalNodesSummaryResult(multimodalNodesSummary, payload);
  renderMultimodalNodesGraphResult(multimodalNodesGraph, multimodalNodesDetail, payload);

  const nodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
  const edges = Array.isArray(payload?.edges) ? payload.edges : [];
  renderTable(multimodalNodesTable, {
    headers: ["Nœud", "Type", "Repère (s)", "Entropie", "Extrait"],
    rows: nodes.map((node) => [
      String(node?.label || ""),
      node?.type === "event" ? "événement visuel" : "segment texte",
      Number.isFinite(Number(node?.time_sec)) ? Number(node.time_sec).toFixed(2) : "",
      Number.isFinite(Number(node?.entropy_peak)) ? Number(node.entropy_peak).toFixed(3) : "",
      String(node?.text_excerpt || node?.direction_label || "").slice(0, 120),
    ]),
  }, {
    title: "Nœuds",
    maxRows: 120,
  });

  renderTable(multimodalEdgesTable, {
    headers: ["Source", "Cible", "Type", "Poids", "Détail"],
    rows: edges.map((edge) => [
      String(edge?.source || ""),
      String(edge?.target || ""),
      String(edge?.type || ""),
      Number.isFinite(Number(edge?.weight)) ? Number(edge.weight).toFixed(3) : "",
      String(edge?.shared_terms || edge?.label || "").slice(0, 120),
    ]),
  }, {
    title: "Liens",
    maxRows: 160,
  });
}

function findMotionMetricsForImage({ file, index, rows, imagePaths = [] }) {
  if (!Array.isArray(rows) || !rows.length) return null;

  const candidates = [];
  const nativePath = getNativeFilePath(file);
  if (nativePath) candidates.push(normalizePath(nativePath));
  const preparedPath = String(imagePaths[index] || "").trim();
  if (preparedPath) candidates.push(normalizePath(preparedPath));
  const fileName = String(file?.name || "").trim().toLowerCase();
  if (fileName) candidates.push(fileName);

  return rows.find((row) => {
    const imagePath = String(row.image_path || row.imagePath || "").trim();
    if (!imagePath) return false;
    const normalized = normalizePath(imagePath);
    const basename = normalized.split("/").pop() || normalized;
    return candidates.some((candidate) => candidate && (normalized === candidate || basename === candidate));
  }) || null;
}

function findArtifactForAbsolutePath(artifacts, outputDir, absolutePath) {
  if (!Array.isArray(artifacts) || !outputDir || !absolutePath) return null;
  const expected = normalizePath(String(absolutePath));
  return artifacts.find((artifact) => {
    const relativePath = String(artifact?.relativePath || "").trim();
    if (!relativePath) return false;
    const candidate = normalizePath(
      `${String(outputDir).replace(/[\\/]+$/, "")}/${relativePath.replace(/^[/\\]+/, "")}`
    );
    return candidate === expected;
  }) || null;
}

function getMotionResultLabel(metrics, fallbackIndex = 1, pathKey = "") {
  const imagePath = String(metrics?.image_path || metrics?.frame_preview_path || "").trim();
  const fileName = imagePath ? imagePath.split(/[\\/]/).pop() : "";
  const timeSec = Number(metrics?.time_sec);
  const frameIndex = Number(metrics?.frame_index || fallbackIndex);
  const isReference = String(metrics?.frame_role || "") === "reference";
  const isRawView = pathKey === "frame_preview_path";

  if (!isRawView && Number.isFinite(frameIndex)) {
    const startIndex = Math.max(1, frameIndex - 1);
    const transitionLabel = `Transition ${startIndex}→${frameIndex}`;
    return Number.isFinite(timeSec)
      ? `${transitionLabel} · ${timeSec.toFixed(2)} s`
      : transitionLabel;
  }

  if (isReference) {
    return fileName ? `${fileName} · référence initiale` : `Image ${frameIndex} · référence initiale`;
  }

  if (fileName) {
    return Number.isFinite(timeSec) ? `${fileName} · ${timeSec.toFixed(2)} s` : fileName;
  }
  return Number.isFinite(timeSec)
    ? `Image ${frameIndex} · ${timeSec.toFixed(2)} s`
    : `Image ${frameIndex}`;
}

function buildMotionCaption(metrics) {
  const parts = [];
  const entropy = Number(metrics?.roi_directional_entropy);
  if (Number.isFinite(entropy) && Math.abs(entropy) > 1e-9) {
    parts.push(`entropie ${entropy.toFixed(3)}`);
  }
  if (String(metrics?.face_analysis_mode || "").trim().toLowerCase() === "manuel" && metrics?.tracked_face_status) {
    parts.push(`suivi ${String(metrics.tracked_face_status)}`);
  }
  return parts.join(" · ");
}

function buildImagePreviewItemFromElement(image, fallback = {}) {
  const title = String(image?.dataset?.previewTitle || image?.alt || fallback.title || "Image").trim() || "Image";
  const kicker = String(image?.dataset?.previewKicker || fallback.kicker || "Résultat").trim() || "Résultat";
  const src = String(image?.currentSrc || image?.src || fallback.src || "").trim();
  return { title, kicker, src };
}

function collectImagePreviewItems(sourceElement, fallbackItem = null) {
  if (!(sourceElement instanceof HTMLImageElement)) {
    return {
      items: fallbackItem?.src ? [fallbackItem] : [],
      index: fallbackItem?.src ? 0 : -1
    };
  }

  let scope = sourceElement.parentElement;
  while (scope && scope !== document.body) {
    const candidates = Array.from(scope.querySelectorAll('img[data-previewable="true"]'))
      .filter((node) => node instanceof HTMLImageElement);
    if (candidates.length > 1 && candidates.includes(sourceElement)) {
      return {
        items: candidates
          .map((image) => buildImagePreviewItemFromElement(image))
          .filter((item) => item.src),
        index: candidates.indexOf(sourceElement)
      };
    }
    scope = scope.parentElement;
  }

  const item = fallbackItem?.src
    ? fallbackItem
    : buildImagePreviewItemFromElement(sourceElement);
  return {
    items: item.src ? [item] : [],
    index: item.src ? 0 : -1
  };
}

function updateImagePreviewNavigationState() {
  const total = appState.imagePreviewItems.length;
  const index = appState.imagePreviewIndex;
  if (imagePreviewCounter) {
    imagePreviewCounter.textContent = total > 0 ? `Image ${index + 1} / ${total}` : "Image 0 / 0";
  }
  if (imagePreviewPrevBtn) {
    imagePreviewPrevBtn.disabled = !(total > 1 && index > 0);
  }
  if (imagePreviewNextBtn) {
    imagePreviewNextBtn.disabled = !(total > 1 && index < total - 1);
  }
}

function renderActiveImagePreview() {
  const item = appState.imagePreviewItems[appState.imagePreviewIndex] || null;
  if (imagePreviewKicker) {
    imagePreviewKicker.textContent = item?.kicker || "Résultat";
  }
  if (imagePreviewTitle) {
    imagePreviewTitle.textContent = item?.title || "Image";
  }
  if (imagePreviewContent) {
    imagePreviewContent.innerHTML = "";
    if (item?.src) {
      const image = document.createElement("img");
      image.src = item.src;
      image.alt = item.title || "Image";
      imagePreviewContent.appendChild(image);
    }
  }
  updateImagePreviewNavigationState();
}

function navigateImagePreview(step) {
  const total = appState.imagePreviewItems.length;
  if (!total) return;
  const nextIndex = Math.max(0, Math.min(total - 1, appState.imagePreviewIndex + step));
  if (nextIndex === appState.imagePreviewIndex) return;
  appState.imagePreviewIndex = nextIndex;
  renderActiveImagePreview();
}

function registerPreviewableImage(image, { title = "", kicker = "Résultat" } = {}) {
  if (!(image instanceof HTMLImageElement)) return image;
  image.classList.add("is-clickable");
  image.dataset.previewable = "true";
  image.dataset.previewTitle = String(title || image.alt || "Image");
  image.dataset.previewKicker = String(kicker || "Résultat");
  image.addEventListener("click", () => {
    openImagePreview(
      image.dataset.previewTitle || image.alt || "Image",
      image.currentSrc || image.src,
      image.dataset.previewKicker || kicker || "Résultat",
      { sourceElement: image }
    );
  });
  return image;
}

function createPreviewableImage({ src, alt, title, kicker = "Analyse mouvements" }) {
  const image = document.createElement("img");
  image.alt = alt || title || "Image";
  image.src = src;
  return registerPreviewableImage(image, { title: title || alt || "Image", kicker });
}

function uniqueNonEmptyStrings(values) {
  const seen = new Set();
  const result = [];
  values.forEach((value) => {
    const normalized = String(value || "").trim();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    result.push(normalized);
  });
  return result;
}

function createMotionViewCard({ label, artifact, fallbackPath = "", alt = "", caption = "", metrics = null }) {
  const card = document.createElement("article");
  card.className = "result-gallery-item";

  const heading = document.createElement("h4");
  heading.textContent = label;
  card.appendChild(heading);

  const href = artifact ? artifactDataToObjectUrl(artifact) : maybeCreateLocalFileUrl(fallbackPath);
  if (href) {
    card.appendChild(
      createPreviewableImage({
        src: href,
        alt: alt || label,
        title: label,
        kicker: "Analyse mouvements"
      })
    );
  }

  if (caption) {
    const text = document.createElement("p");
    text.className = "result-gallery-caption";
    text.textContent = caption;
    card.appendChild(text);
  }

  if (metrics) {
    appendMotionMetricList(card, metrics);
  }

  return card;
}

function renderMotionResultGallery(container, rows, artifacts, outputDir, pathKey, emptyMessage) {
  clearContainer(container);
  if (!Array.isArray(rows) || !rows.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const visibleRows = rows.filter((metrics) => String(metrics?.[pathKey] || "").trim());
  if (!visibleRows.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  const gallery = document.createElement("div");
  gallery.className = "result-gallery";

  visibleRows.forEach((metrics, index) => {
    const absolutePath = String(metrics?.[pathKey] || "").trim();
    const artifact = absolutePath ? findArtifactForAbsolutePath(artifacts, outputDir, absolutePath) : null;
    const label = getMotionResultLabel(metrics, index + 1, pathKey);
    const card = createMotionViewCard({
      label,
      artifact,
      fallbackPath: absolutePath,
      alt: `${pathKey} · ${label}`,
      caption: buildMotionCaption(metrics),
      metrics,
    });
    gallery.appendChild(card);
  });

  container.appendChild(gallery);
}

function appendMotionMetricList(container, metrics) {
  const list = document.createElement("dl");
  list.className = "motion-metrics-list";
  const backendLabels = {
    opencv_face_bbox: "OpenCV visage",
    hog_person_detector: "OpenCV corps",
    frame_fallback: "Fallback image entière",
    mediapipe_face_mesh: "MediaPipe Face Mesh",
    mediapipe_pose: "MediaPipe Pose",
    mediapipe_pose_fallback: "MediaPipe pose (fallback)"
  };
  const anatomyMode = String(metrics?.anatomy_mode || "").trim().toLowerCase();
  const faceAnalysisMode = String(metrics?.face_analysis_mode || "").trim().toLowerCase();
  const faceCount = Number(metrics?.face_count);
  const fields = [
    ["motion_mean", "Optical flow moyen"],
    ["motion_peak_p95", "Magnitude p95"],
    ["direction_label", "Direction"],
    ["roi_directional_entropy", "Entropie directionnelle"],
    ["roi_directional_entropy_norm", "Entropie directionnelle norm."],
  ];

  if (anatomyMode === "visage") {
    if (faceAnalysisMode === "manuel") {
      fields.push(
        ["tracked_face_status", "Suivi du visage"],
        ["tracked_face_confidence", "Confiance du suivi"],
        ["tracked_face_identity_similarity", "Similarité identité"],
        ["tracked_face_lost", "Visage perdu"],
      );
    }
    if (Number.isFinite(faceCount) && faceCount > 1) {
      fields.push(["face_count", "Visages détectés"]);
    }
    if (!Number.isFinite(faceCount) || faceCount > 0) {
      fields.push(
        ["roi_motion_energy", "Énergie visage"],
        ["mouth_opening", "Ouverture bouche"],
        ["left_right_asymmetry", "Asymétrie G/D"],
      );
    }
  } else if (anatomyMode === "corps_entier") {
    fields.push(
      ["roi_motion_energy", "Énergie corps"],
      ["body_center_displacement", "Déplacement centre corps"],
    );
  } else {
    fields.push(
      ["roi_motion_energy", "Énergie ROI"],
    );
  }

  const suppressZeroFields = new Set([
    "roi_motion_energy",
    "roi_directional_entropy",
    "roi_directional_entropy_norm",
    "mouth_opening",
    "left_right_asymmetry",
    "body_center_displacement",
    "tracked_face_confidence",
    "tracked_face_identity_similarity",
  ]);

  fields.forEach(([key, label]) => {
    const rawValue = metrics[key];
    if (rawValue === undefined || rawValue === null || rawValue === "") return;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    const numericValue = Number(rawValue);
    if (key === "anatomy_backend" || key === "tracked_face_identity_backend") {
      dd.textContent = backendLabels[String(rawValue)] || String(rawValue);
    } else if ((key === "tracked_face_confidence" || key === "tracked_face_identity_similarity") && Number.isFinite(numericValue)) {
      dd.textContent = `${(numericValue * 100).toFixed(0)} %`;
    } else if (Number.isFinite(numericValue) && suppressZeroFields.has(key) && Math.abs(numericValue) < 1e-9) {
      return;
    } else if (Number.isFinite(numericValue) && key !== "face_count") {
      dd.textContent = numericValue.toFixed(3);
    } else {
      dd.textContent = String(rawValue);
    }
    list.appendChild(dt);
    list.appendChild(dd);
  });

  if (list.childElementCount) {
    container.appendChild(list);
  }
}

function createMotionGalleryCard({ title, rawArtifact, panelArtifact, metrics, rawAlt, panelAlt }) {
  const card = document.createElement("article");
  card.className = "result-gallery-item";

  const heading = document.createElement("h4");
  heading.textContent = title;
  card.appendChild(heading);

  if (rawArtifact) {
    const rawImage = document.createElement("img");
    rawImage.alt = rawAlt || title;
    rawImage.src = artifactDataToObjectUrl(rawArtifact);
    card.appendChild(rawImage);
  }

  if (panelArtifact) {
    const subtitle = document.createElement("p");
    subtitle.className = "result-gallery-subtitle";
    subtitle.textContent = "Magnitude · HSV · Superposition · Vecteurs";
    card.appendChild(subtitle);

    const analysisImage = document.createElement("img");
    analysisImage.className = "result-gallery-analysis-image";
    analysisImage.alt = panelAlt || `Analyse optique pour ${title}`;
    analysisImage.src = artifactDataToObjectUrl(panelArtifact);
    card.appendChild(analysisImage);
  }

  if (metrics) {
    appendMotionMetricList(card, metrics);
  }

  return card;
}

function renderMultimodalMotionResults() {
  const motionResult = appState.multimodalResults?.mouvements;
  const parsedFrames = motionResult?.framesCsvArtifact ? parseCsv(artifactDataToText(motionResult.framesCsvArtifact)) : null;
  const motionRows = parsedFrames?.headers?.length
    ? parsedFrames.rows.map((row) => {
        const mapped = {};
        parsedFrames.headers.forEach((header, index) => {
          mapped[header] = row[index];
        });
        return mapped;
      })
    : [];
  const hiddenMotionHeaders = [
    "motion_angle_deg",
    "contrast_std",
    "heat_x_norm",
    "heat_y_norm",
    "roi_center_x_norm",
    "roi_center_y_norm",
  ];
  const motionArtifacts = motionResult?.artifacts || [];
  const motionOutputDir = motionResult?.outputDir || "";

  clearContainer(multimodalMotionTimelinePlot);
  if (motionResult?.chartPngArtifact) {
    const image = document.createElement("img");
    image.className = "result-image";
    image.alt = "Timeline de l'analyse des mouvements";
    image.src = artifactDataToObjectUrl(motionResult.chartPngArtifact);
    multimodalMotionTimelinePlot.appendChild(image);
  } else {
    multimodalMotionTimelinePlot?.appendChild(createEmptyState("Aucune timeline mouvements n'est disponible."));
  }

  renderMotionResultGallery(
    multimodalMotionRawGallery,
    motionRows,
    motionArtifacts,
    motionOutputDir,
    "frame_preview_path",
    "Aucune image brute n'est disponible."
  );
  renderMotionResultGallery(
    multimodalMotionMagnitudeGallery,
    motionRows,
    motionArtifacts,
    motionOutputDir,
    "magnitude_preview_path",
    "Aucune vignette de magnitude n'est disponible."
  );
  renderMotionResultGallery(
    multimodalMotionEntropyGallery,
    motionRows,
    motionArtifacts,
    motionOutputDir,
    "directional_entropy_preview_path",
    "Aucune vignette d'entropie directionnelle n'est disponible."
  );
  renderMotionResultGallery(
    multimodalMotionHsvGallery,
    motionRows,
    motionArtifacts,
    motionOutputDir,
    "hsv_preview_path",
    "Aucune vignette HSV n'est disponible."
  );
  renderMotionResultGallery(
    multimodalMotionVectorsGallery,
    motionRows,
    motionArtifacts,
    motionOutputDir,
    "vectors_preview_path",
    "Aucune vignette de vecteurs n'est disponible."
  );
  renderMotionResultGallery(
    multimodalMotionOverlayGallery,
    motionRows,
    motionArtifacts,
    motionOutputDir,
    "overlay_preview_path",
    "Aucune vignette de superposition n'est disponible."
  );
  renderMotionResultGallery(
    multimodalMotionAnatomyGallery,
    motionRows,
    motionArtifacts,
    motionOutputDir,
    "annotated_preview_path",
    "Aucune vignette annotée n'est disponible."
  );

  renderTable(
    multimodalMotionWindowsTable,
    motionResult?.windowsCsvArtifact
      ? omitParsedColumns(parseCsv(artifactDataToText(motionResult.windowsCsvArtifact)), hiddenMotionHeaders)
      : null,
    {
      title: "Fenêtres temporelles",
      maxRows: 30,
      emptyMessage: "Aucune fenêtre temporelle n'est disponible."
    }
  );

  renderTable(
    multimodalMotionFramesTable,
    motionResult?.framesCsvArtifact
      ? omitParsedColumns(parseCsv(artifactDataToText(motionResult.framesCsvArtifact)), hiddenMotionHeaders)
      : null,
    {
      title: "Mesures par image",
      maxRows: 30,
      emptyMessage: "Aucune mesure par image n'est disponible."
    }
  );
}

function renderMultimodalImagesGallery() {
  clearContainer(multimodalImagesGallery);
  const files = getSelectedMultimodalImageFiles();

  if (!files.length) {
    multimodalImagesGallery.appendChild(createEmptyState("Aucune vignette disponible."));
    return;
  }

  const gallery = document.createElement("div");
  gallery.className = "result-gallery";
  files.forEach((file, index) => {
    const card = document.createElement("article");
    card.className = "result-gallery-item";
    const header = document.createElement("div");
    header.className = "result-gallery-item-header";

    const heading = document.createElement("h4");
    heading.textContent = file.name || `Image ${index + 1}`;
    header.appendChild(heading);

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "result-gallery-remove-button";
    removeButton.setAttribute("aria-label", `Supprimer ${file.name || `l'image ${index + 1}`}`);
    removeButton.title = "Supprimer cette image";
    removeButton.textContent = "×";
    removeButton.addEventListener("click", async () => {
      appState.multimodalSelectedImageFiles = getSelectedMultimodalImageFiles().filter((_, fileIndex) => fileIndex !== index);
      clearMultimodalFaceSelection({ rerender: false });
      await persistSelectedMultimodalImages();
    });
    header.appendChild(removeButton);
    card.appendChild(header);

    const imageUrl = createObjectUrl(file);
    card.appendChild(
      createPreviewableImage({
        src: imageUrl,
        alt: file.name || `Image ${index + 1}`,
        title: file.name || `Image ${index + 1}`,
        kicker: "Images importées"
      })
    );
    gallery.appendChild(card);
  });
  multimodalImagesGallery.appendChild(gallery);
}

function renderMultimodalWorkspace() {
  const isCustomInterval = getMultimodalIntervalModeValue() === "custom";
  const extractsImages = shouldPrepareMultimodalImages();
  const isBodyMode = multimodalMotionAnatomyMode?.value === "corps_entier";
  const isManualFaceMode = multimodalMotionFaceAnalysisMode?.value === "manuel";
  [
    multimodalExtractStartHours,
    multimodalExtractStartMinutes,
    multimodalExtractStartSeconds,
    multimodalExtractEndHours,
    multimodalExtractEndMinutes,
    multimodalExtractEndSeconds,
  ].forEach((input) => {
    if (input) input.disabled = !isCustomInterval;
  });
  [multimodalFrameRate1, multimodalFrameRate25, multimodalFrameQualityLow, multimodalFrameQualityHigh].forEach((input) => {
    if (input) input.disabled = !extractsImages;
  });
  if (multimodalMotionFaceAnalysisMode) {
    multimodalMotionFaceAnalysisMode.disabled = isBodyMode;
    if (isBodyMode) {
      multimodalMotionFaceAnalysisMode.value = "principal";
    }
  }
  if (multimodalSelectFaceBtn) {
    multimodalSelectFaceBtn.disabled = isBodyMode || !isManualFaceMode || !getSelectedMultimodalImageFiles().length;
  }
  if (multimodalClearFaceSelectionBtn) {
    multimodalClearFaceSelectionBtn.disabled = !appState.multimodalSelectedFaceSelection;
  }
  updateMultimodalFaceSelectionStatus();

  if (multimodalYoutubeStatus) {
    const youtubeUrl = getMultimodalYoutubeUrl();
    setReadonlyStatus(
      multimodalYoutubeStatus,
      youtubeUrl ? `URL YouTube : ${youtubeUrl}` : "Aucune URL YouTube renseignée."
    );
  }

  if (multimodalYoutubePreview) {
    clearContainer(multimodalYoutubePreview);
    const youtubeUrl = getMultimodalYoutubeUrl();
    const videoId = extractYouTubeVideoId(youtubeUrl);
    if (!youtubeUrl) {
      multimodalYoutubePreview.appendChild(createEmptyState("Aperçu YouTube indisponible tant qu'aucune URL n'est renseignée."));
    } else if (!videoId) {
      multimodalYoutubePreview.appendChild(createEmptyState("Impossible d'afficher l'aperçu : l'URL YouTube n'est pas reconnue."));
    } else {
      const wrapper = document.createElement("div");
      wrapper.className = "multimodal-youtube-embed";
      const iframe = document.createElement("iframe");
      iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}`;
      iframe.title = "Lecteur YouTube multimodal";
      iframe.loading = "lazy";
      iframe.allow =
        "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
      iframe.referrerPolicy = "strict-origin-when-cross-origin";
      iframe.allowFullscreen = true;
      wrapper.appendChild(iframe);
      multimodalYoutubePreview.appendChild(wrapper);
    }
  }

  if (multimodalCookiesStatus) {
    const errorMessage = getMultimodalInputError("cookies");
    if (errorMessage) {
      setReadonlyStatus(multimodalCookiesStatus, errorMessage, { isError: true });
    } else {
      setReadonlyStatus(
        multimodalCookiesStatus,
        formatSelectedFileStatus(
          getMultimodalCookiesFile(),
          "Aucun fichier cookies sélectionné.",
          {
            preparedPath: getMultimodalCookiesPath(),
            pending: isMultimodalInputPending("cookies"),
          }
        )
      );
    }
  }

  if (multimodalAudioStatus) {
    const errorMessage = getMultimodalInputError("audio");
    if (errorMessage) {
      setReadonlyStatus(multimodalAudioStatus, errorMessage, { isError: true });
    } else {
      const selectedAudio = getMultimodalAudioFile();
      const preparedAudioPath = getMultimodalAudioPath();
      setReadonlyStatus(
        multimodalAudioStatus,
        selectedAudio
          ? formatSelectedFileStatus(
              selectedAudio,
              "Aucun fichier audio sélectionné.",
              {
                preparedPath: preparedAudioPath,
                pending: isMultimodalInputPending("audio"),
              }
            )
          : preparedAudioPath
            ? `Piste audio préparée automatiquement : ${preparedAudioPath}`
            : "Aucun fichier audio sélectionné."
      );
    }
  }

  if (multimodalVideoStatus) {
    const errorMessage = getMultimodalInputError("video");
    if (errorMessage) {
      setReadonlyStatus(multimodalVideoStatus, errorMessage, { isError: true });
    } else {
      const selectedVideo = getMultimodalVideoFile();
      const preparedVideoPath = getMultimodalVideoPath();
      setReadonlyStatus(
        multimodalVideoStatus,
        selectedVideo
          ? formatSelectedFileStatus(
              selectedVideo,
              "Aucun fichier vidéo sélectionné.",
              {
                preparedPath: preparedVideoPath,
                pending: isMultimodalInputPending("video"),
              }
            )
          : preparedVideoPath
            ? `Vidéo préparée automatiquement : ${preparedVideoPath}`
            : "Aucun fichier vidéo sélectionné."
      );
    }
  }

  if (multimodalImagesStatus) {
    const errorMessage = getMultimodalInputError("images");
    if (errorMessage) {
      setReadonlyStatus(multimodalImagesStatus, errorMessage, { isError: true });
    } else {
      const files = getSelectedMultimodalImageFiles();
      const imagesDir = getMultimodalImagesDir();
      if (isMultimodalInputPending("images")) {
        setReadonlyStatus(multimodalImagesStatus, "Préparation locale des images...");
      } else if (files.length) {
        setReadonlyStatus(
          multimodalImagesStatus,
          `${files.length} image(s) sélectionnée(s)${imagesDir ? ` · dossier prêt : ${imagesDir}` : ""}`
        );
      } else if (imagesDir) {
        setReadonlyStatus(multimodalImagesStatus, `Séquence d'images prête : ${imagesDir}`);
      } else {
        setReadonlyStatus(multimodalImagesStatus, "Aucune image sélectionnée.");
      }
    }
    renderMultimodalImagesGallery();
  }

  if (multimodalSegmentsStatus) {
    const errorMessage = getMultimodalInputError("segments");
    if (errorMessage) {
      setReadonlyStatus(multimodalSegmentsStatus, errorMessage, { isError: true });
    } else {
      const selectedSegments = getSelectedMultimodalSegmentsFile();
      const preparedSegmentsPath = getMultimodalSegmentsPath();
      setReadonlyStatus(
        multimodalSegmentsStatus,
        selectedSegments
          ? formatSelectedFileStatus(
              selectedSegments,
              "Aucun CSV de segments sélectionné.",
              {
                preparedPath: preparedSegmentsPath,
                pending: isMultimodalInputPending("segments"),
              }
            )
          : preparedSegmentsPath
            ? `CSV texte utilisé automatiquement pour l'alignement : ${preparedSegmentsPath}`
            : "Aucun CSV de segments sélectionné."
      );
    }
  }

  if (multimodalAlignSourcesStatus) {
    const lines = [];
    const generatedVideo = getMultimodalGeneratedPath("video");
    const generatedAudio = getMultimodalGeneratedPath("audio");
    const generatedSegments = getMultimodalGeneratedPath("segments");
    const generatedAlignedSegments = getMultimodalGeneratedPath("segmentsAligned");
    const generatedFrames = getMultimodalGeneratedPath("framesIndex");
    const motionFramesCsv = getMultimodalMotionFramesCsvPath();
    const audioAnomaliesCsv = getMultimodalAudioAnomaliesCsvPath();
    if (generatedVideo) lines.push(`Vidéo MP4 : ${generatedVideo}`);
    if (generatedAudio) {
      lines.push(
        generatedAudio.toLowerCase().endsWith(".wav")
          ? `Piste WAV : ${generatedAudio}`
          : `Piste MP3 : ${generatedAudio}`
      );
    }
    if (generatedSegments) lines.push(`Segments audio bruts CSV (entrée) : ${generatedSegments}`);
    if (audioAnomaliesCsv) lines.push(`Anomalies audio CSV (entrée) : ${audioAnomaliesCsv}`);
    if (motionFramesCsv) lines.push(`Indicateurs mouvements CSV (entrée, référence temporelle visuelle) : ${motionFramesCsv}`);
    if (generatedAlignedSegments) lines.push(`CSV multimodal synchronisé (sortie) : ${generatedAlignedSegments}`);
    if (generatedFrames) lines.push(`Index des images : ${generatedFrames}`);
    if (generatedSegments && !generatedVideo && !getMultimodalImagesDir()) {
      lines.push("Limite actuelle : l'alignement image/texte nécessite soit une séquence d'images, soit une vidéo préparée. Avec un fichier audio seul, les segments sont bien produits mais il n'y a pas de support visuel à aligner.");
    }
    setReadonlyStatus(
      multimodalAlignSourcesStatus,
      lines.length
        ? lines.join("\n")
        : "Aucune source multimodale préparée pour l'alignement."
    );
  }

  if (multimodalAlignOverlayStatus) {
    const overlays = [];
    if (multimodalAlignOverlayImages?.checked) overlays.push("images");
    if (multimodalAlignOverlaySegments?.checked) overlays.push("segments de texte");
    if (multimodalAlignOverlayAudio?.checked) overlays.push("audio");
    setReadonlyStatus(
      multimodalAlignOverlayStatus,
      overlays.length
        ? `Superposition courante : ${overlays.join(", ")}.`
        : "Aucun indicateur sélectionné pour la superposition."
    );
  }

  [
    { side: "a", statusElement: multimodalCompareSourceStatusA },
    { side: "b", statusElement: multimodalCompareSourceStatusB },
  ].forEach(({ side, statusElement }) => {
    if (!statusElement) return;
    const errorMessage = getMultimodalComparisonError(side);
    if (errorMessage) {
      setReadonlyStatus(statusElement, errorMessage, { isError: true });
      return;
    }
    const source = getMultimodalComparisonSource(side);
    const file = getMultimodalComparisonVideoFile(side);
    const preparedVideoPath = getMultimodalComparisonPreparedVideoPath(side);
    const startSec = getMultimodalComparisonStartSec(side);
    const endSec = getMultimodalComparisonEndSec(side);
    const intervalLabel = startSec !== null || endSec !== null
      ? ` · intervalle ${formatHmsLabel(startSec)} → ${formatHmsLabel(endSec, { allowOpenEnded: true })}`
      : "";
    if (file) {
      setReadonlyStatus(
        statusElement,
        formatSelectedFileStatus(
          file,
          `Aucune source ${side.toUpperCase()} sélectionnée.`,
          {
            preparedPath: preparedVideoPath,
            pending: false,
          }
        ) + intervalLabel
      );
      return;
    }
    if (source?.kind === "youtube") {
      setReadonlyStatus(statusElement, `URL ${side.toUpperCase()} : ${source.value}${intervalLabel}`);
      return;
    }
    if (preparedVideoPath) {
      setReadonlyStatus(statusElement, `Vidéo ${side.toUpperCase()} prête : ${preparedVideoPath}${intervalLabel}`);
      return;
    }
    setReadonlyStatus(statusElement, `Aucune source ${side.toUpperCase()} sélectionnée.`);
  });

  ["a", "b"].forEach((side) => {
    const canManualSelect =
      multimodalMotionAnatomyMode?.value !== "corps_entier" &&
      multimodalMotionFaceAnalysisMode?.value === "manuel";
    const sourceAvailable = Boolean(getMultimodalComparisonSource(side)?.value);
    const selectButton = getMultimodalComparisonSelectFaceButton(side);
    const clearButton = getMultimodalComparisonClearFaceButton(side);
    if (selectButton) {
      selectButton.disabled = !canManualSelect || !sourceAvailable;
    }
    if (clearButton) {
      clearButton.disabled = !getMultimodalComparisonFaceSelection(side);
    }
    updateMultimodalComparisonFaceSelectionStatus(side);
  });

  renderMultimodalComparisonPreview("a");
  renderMultimodalComparisonPreview("b");

  if (multimodalCompareOutputDirStatus) {
    const comparisonDir = getMultimodalComparisonBaseOutputDir();
    setReadonlyStatus(
      multimodalCompareOutputDirStatus,
      comparisonDir
        ? `Dossier A/B choisi : ${comparisonDir}`
        : "Dossier A/B par défaut : multimodale/exports/comparaison_ab"
    );
  }

  if (multimodalOutputDirStatus) {
    const baseDir = getMultimodalBaseOutputDir();
    setReadonlyStatus(
      multimodalOutputDirStatus,
      baseDir
        ? `Dossier choisi : ${baseDir}`
        : "Dossier par défaut : multimodale/exports"
    );
  }

  if (multimodalExtractStatus) {
    const requestedOutputs = [];
    if (shouldPrepareMultimodalMp4()) requestedOutputs.push("MP4");
    if (shouldPrepareMultimodalMp3()) requestedOutputs.push("MP3");
    if (shouldPrepareMultimodalWav()) requestedOutputs.push("WAV");
    if (shouldPrepareMultimodalTimestampedSegments()) requestedOutputs.push("segments horodatés");
    if (shouldPrepareMultimodalImages()) {
      requestedOutputs.push(`${getMultimodalFrameRateValue()} fps`);
    }
    const qualityLabel = getMultimodalFrameQualityValue() === "high"
      ? "très haute définition (1920 px)"
      : "définition standard (1024 px)";
    const rateLabel = `${getMultimodalFrameRateValue()} image${getMultimodalFrameRateValue() > 1 ? "s" : ""} par seconde`;
    const startSec = getMultimodalStartSec();
    const endSec = getMultimodalEndSec();
    const intervalLabel = isCustomInterval
      ? `intervalle personnalisé (${formatHmsLabel(startSec)} → ${formatHmsLabel(endSec, { allowOpenEnded: true })})`
      : "toute la vidéo";
    setReadonlyStatus(
      multimodalExtractStatus,
      requestedOutputs.length
        ? `Préparation demandée : ${requestedOutputs.join(", ")} sur ${intervalLabel}${shouldPrepareMultimodalImages() ? `, en ${rateLabel}, en ${qualityLabel}` : ""}.`
        : "Aucun fichier de sortie n'est actuellement sélectionné."
    );
  }

  if (runMultimodalYtdlpBtn) {
    const hasExtractionRequest = Boolean(buildMultimodalYtdlpArgs());
    const hasSegmentsRequest = shouldPrepareMultimodalTimestampedSegments() && Boolean(buildMultimodalAudioArgs());
    runMultimodalYtdlpBtn.disabled = isMultimodalScriptRunning("extraction.py") || !(hasExtractionRequest || hasSegmentsRequest);
  }
  if (runMultimodalAudioBtn) {
    runMultimodalAudioBtn.disabled = isMultimodalScriptRunning("audio.py") || !buildMultimodalAudioArgs();
  }
  if (runMultimodalMotionBtn) {
    runMultimodalMotionBtn.disabled = isMultimodalScriptRunning("mouvements.py") || !buildMultimodalMotionArgs();
  }
  if (runMultimodalAlignBtn) {
    runMultimodalAlignBtn.disabled = isMultimodalScriptRunning("alignement.py") || !buildMultimodalAlignArgs();
  }
  if (runMultimodalNodesBtn) {
    runMultimodalNodesBtn.disabled = isMultimodalScriptRunning("noeuds.py") || !buildMultimodalNodesArgs();
  }
  if (runMultimodalCompareAbBtn) {
    runMultimodalCompareAbBtn.disabled = isMultimodalComparisonAbRunning()
      || !getMultimodalComparisonSource("a")
      || !getMultimodalComparisonSource("b")
      || Object.values(appState.multimodalRunningScripts || {}).some(Boolean);
  }

  renderMultimodalAudioResults();
  renderMultimodalMotionResults();
  renderMultimodalAlignmentResults();
  renderMultimodalNodesResults();
  renderMultimodalComparisonAbResults();
}

function getMultimodalProgressKey(scriptName) {
  if (scriptName === "mouvements.py") return "mouvements";
  return "";
}

function getMultimodalRunningKey(scriptName) {
  if (scriptName === "audio.py") return "audio";
  if (scriptName === "mouvements.py") return "mouvements";
  if (scriptName === "alignement.py") return "alignement";
  if (scriptName === "noeuds.py") return "noeuds";
  return "extraction";
}

function isMultimodalScriptRunning(scriptName) {
  const key = getMultimodalRunningKey(scriptName);
  return Boolean(appState.multimodalRunningScripts?.[key]);
}

function setMultimodalScriptRunning(scriptName, isRunning) {
  const key = getMultimodalRunningKey(scriptName);
  if (!appState.multimodalRunningScripts) {
    appState.multimodalRunningScripts = {};
  }
  appState.multimodalRunningScripts[key] = Boolean(isRunning);
}

function waitForNextPaintFrame() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });
}

async function runMultimodalScript(request, options = {}) {
  const {
    title = "Traitement multimodal",
    message = "Execution en cours...",
    statusElement = null,
    actionButton = null,
    plannedStages = [],
    progressController = multimodalProgression,
    openProgress = true,
    closeProgressOnSuccess = true,
    closeProgressOnError = true,
    progressRange = [0, 100],
    hydrateAssets = true,
    recordHistory = true,
  } = options;
  if (!request?.scriptName || !Array.isArray(request.args) || !request.outputDir) {
    log("[error] Paramètres multimodaux incomplets.");
    setReadonlyStatus(statusElement, "Paramètres multimodaux incomplets.", { isError: true });
    return null;
  }

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    log("[error] Les boutons multimodaux automatiques ne sont disponibles que dans Tauri.");
    setReadonlyStatus(statusElement, "Cette action n'est disponible que dans l'application Tauri.", { isError: true });
    return null;
  }

  if (isMultimodalScriptRunning(request.scriptName)) {
    const infoMessage = "Un traitement est déjà en cours pour cette analyse.";
    log(`[info] ${infoMessage}`);
    setReadonlyStatus(statusElement, infoMessage);
    return null;
  }

  setMultimodalScriptRunning(request.scriptName, true);

  if (actionButton) {
    actionButton.disabled = true;
  }
  setReadonlyStatus(statusElement, "Traitement en cours...");
  const progressStart = Number.isFinite(Number(progressRange?.[0])) ? Number(progressRange[0]) : 0;
  const progressEnd = Number.isFinite(Number(progressRange?.[1])) ? Number(progressRange[1]) : 100;
  const progressMin = Math.max(0, Math.min(100, progressStart));
  const progressMax = Math.max(progressMin, Math.min(100, progressEnd));
  const scaleProgress = (value) => {
    const clamped = Math.max(0, Math.min(100, Number(value) || 0));
    return Math.round(progressMin + ((progressMax - progressMin) * (clamped / 100)));
  };

  if (openProgress) {
    progressController.open(title, message);
  }
  progressController.set(scaleProgress(4), "Vérification de l'environnement Python...");
  await waitForNextPaintFrame();

  let stageTimer = null;
  let progressPoller = null;
  let stageIndex = 0;
  const stagePlan = Array.isArray(plannedStages) ? plannedStages.filter(Boolean) : [];
  const progressKey = getMultimodalProgressKey(request.scriptName);
  const tauriInvokeSafe = tauriInvoke;
  const advanceStage = () => {
    if (!stagePlan.length) return;
    const stage = stagePlan[Math.min(stageIndex, stagePlan.length - 1)];
    const progressValue = Math.min(88, 18 + (stageIndex * Math.max(8, Math.floor(62 / Math.max(1, stagePlan.length)))));
    progressController.set(scaleProgress(progressValue), stage);
    stageIndex += 1;
  };
  if (progressKey) {
    progressPoller = window.setInterval(async () => {
      try {
        const snapshot = await tauriInvokeSafe("read_multimodal_progress", {
          outputDir: request.outputDir,
          analysisKey: progressKey,
        });
        if (snapshot?.exists) {
          const value = Number(snapshot.progress);
          const messageText = String(snapshot.message || "").trim() || String(snapshot.stage || "").trim() || "Traitement multimodal en cours...";
          if (Number.isFinite(value)) {
            progressController.set(scaleProgress(Math.max(0, Math.min(100, Math.round(value)))), messageText);
          } else {
            progressController.set(scaleProgress(18), messageText);
          }
        }
      } catch (_error) {
      }
    }, 250);
  } else if (stagePlan.length) {
    advanceStage();
    stageTimer = window.setInterval(() => {
      if (stageIndex < stagePlan.length) {
        advanceStage();
      }
    }, 2200);
  }

  try {
    const bootstrap = await ensureDependenciesReady();
    if (!bootstrap?.success) {
      const bootstrapMessage = bootstrap?.message || "Le runtime Python n'est pas prêt.";
      log(`[error] ${bootstrapMessage}`);
      setReadonlyStatus(statusElement, bootstrapMessage, { isError: true });
      progressController.set(scaleProgress(0), "Environnement Python incomplet.");
      return null;
    }

    progressController.set(scaleProgress(8), "Préparation du script multimodal...");
    const response = await tauriInvoke("run_multimodal_script", {
      scriptName: request.scriptName,
      args: request.args,
      outputDir: request.outputDir,
    });

    progressController.set(scaleProgress(92), "Collecte des exports...");
    log(`[info] Script multimodal lancé : ${request.scriptName}`);
    if (Array.isArray(response.logs)) {
      response.logs.forEach((line) => log(line));
    }
    if (hydrateAssets) {
      hydrateGeneratedMultimodalAssets(request.scriptName, response);
    }
    if (recordHistory && Array.isArray(response.files) && response.files.length) {
      const folderName = `${request.scriptName.replace(/\.py$/, "")}-${Date.now()}`;
      const virtualFiles = response.files.map((artifact) => createVirtualFileFromArtifact(artifact, folderName));
      appState.outputDir = response.outputDir || null;
      renderResults(virtualFiles);
      rememberAnalysisHistoryEntry({
        id: `${request.scriptName}-${Date.now()}`,
        analysisKind: getMultimodalHistoryKind(request.scriptName),
        createdAt: new Date().toISOString(),
        corpusName: getAnalysisKindLabel(getMultimodalHistoryKind(request.scriptName)),
        folderName,
        outputDir: response.outputDir || null,
        navigationTarget: "multimodale",
        logs: Array.isArray(response.logs) ? response.logs : [],
        artifacts: response.files
      });
    }
    if (response.outputDir) {
      log(`[info] Exports multimodaux : ${response.outputDir}`);
    }
    setReadonlyStatus(
      statusElement,
      response.outputDir
        ? `Terminé. Exports écrits dans : ${response.outputDir}`
        : "Traitement terminé."
    );
    if (request.scriptName === "audio.py" && getMultimodalGeneratedPath("video") && getMultimodalGeneratedPath("segments")) {
      activateMultimodalSubTab("multimodale_alignement");
    }
    progressController.set(scaleProgress(100), "Traitement multimodal terminé.");
    if (closeProgressOnSuccess) {
      setTimeout(() => progressController.close(), 700);
    }
    return response;
  } catch (error) {
    log(`[error] ${error?.message || String(error)}`);
    setReadonlyStatus(statusElement, error?.message || String(error), { isError: true });
    progressController.set(scaleProgress(100), "Le traitement s'est arrêté sur une erreur.");
    if (closeProgressOnError) {
      progressController.close();
    }
    return null;
  } finally {
    setMultimodalScriptRunning(request.scriptName, false);
    if (stageTimer) {
      window.clearInterval(stageTimer);
    }
    if (progressPoller) {
      window.clearInterval(progressPoller);
    }
    renderMultimodalWorkspace();
  }
}

function getSubcorpusFileName({ term = "", classLabel = "", scope = "classe" } = {}) {
  const corpusBaseName = getArchiveBaseName();
  const normalizedTerm = String(term || "").trim() || "forme";
  const normalizedClass = String(classLabel || "").trim();
  if (scope === "classes") {
    return `${corpusBaseName}_sous-corpus_${normalizedTerm}_toutes-les-classes.txt`;
  }
  if (normalizedClass) {
    return `${corpusBaseName}_sous-corpus_${normalizedTerm}_classe-${normalizedClass}.txt`;
  }
  return `${corpusBaseName}_sous-corpus_${normalizedTerm}.txt`;
}

function slugifyExportPart(value, fallback = "element") {
  const source = String(value || "").trim();
  if (!source) return fallback;
  const normalized = source
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
  return normalized || fallback;
}

function getJsdConcordancierFileName({ term = "", uniteDepart = "", uniteArrivee = "", modeComparaison = "" } = {}) {
  const corpusBaseName = getArchiveBaseName();
  const safeTerm = slugifyExportPart(term, "terme");
  const safeDepart = slugifyExportPart(uniteDepart, "depart");
  const safeArrivee = slugifyExportPart(uniteArrivee, "arrivee");
  const safeMode = slugifyExportPart(modeComparaison, "jsd");
  return `${corpusBaseName}_concordancier_jsd_${safeMode}_${safeTerm}_${safeDepart}_vers_${safeArrivee}.txt`;
}

async function downloadResultsArchive({ outputDir, entryCount = 0, archiveBaseName, pendingButton = null } = {}) {
  if (!outputDir || !entryCount) {
    log("[error] Aucun résultat disponible à télécharger.");
    setDownloadResultsStatus("Aucun résultat n'est disponible pour créer l'archive.", { isError: true });
    return;
  }

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    log("[error] Le téléchargement des résultats n'est disponible que dans Tauri.");
    setDownloadResultsStatus("Cette action n'est disponible que dans l'application Tauri.", { isError: true });
    return;
  }

  const button = pendingButton instanceof HTMLButtonElement ? pendingButton : downloadResultsBtn;
  const defaultLabel = button?.textContent || "Télécharger";

  try {
    if (button) {
      button.disabled = true;
      button.textContent = "Préparation...";
    }
    setSidebarRuntimeStatus("Preparation de l'archive");
    setDownloadResultsStatus("Création de l'archive des résultats en cours...", { isError: false });
    const safeArchiveBaseName = String(archiveBaseName || "").trim() || "iramuteq-resultats";
    log(`[info] Préparation de l'archive des résultats (${entryCount} fichier(s)).`);

    try {
      const payload = await tauriInvoke("save_results_archive", {
        outputDir,
        archiveName: `${safeArchiveBaseName}.zip`
      });
      setSidebarRuntimeStatus("Archive enregistree", "success");
      setDownloadResultsStatus(`Archive enregistrée : ${payload.savedPath || payload.filename}`, { isError: false });
      log(`[info] Archive des résultats enregistrée : ${payload.savedPath || payload.filename}`);
      await revealInFileManager(payload.savedPath || payload.filename);
      log("[info] Emplacement de l'archive ouvert dans le gestionnaire de fichiers.");
    } catch (nativeError) {
      log("[info] Enregistrement natif indisponible, tentative de téléchargement direct.");
      const payload = await tauriInvoke("download_results_archive", {
        outputDir,
        archiveName: `${safeArchiveBaseName}.zip`
      });
      const bytes = decodeBase64ToBytes(payload.data);
      const blob = new Blob([bytes], { type: payload.mimeType || "application/zip" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = payload.filename || `${safeArchiveBaseName}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSidebarRuntimeStatus("Archive preparee", "success");
      setDownloadResultsStatus(
        `Le navigateur a préparé l'archive ${payload.filename || `${safeArchiveBaseName}.zip`}. Vérifie ton dossier Téléchargements.`,
        { isError: false }
      );
      log(`[info] Archive des résultats préparée : ${payload.filename || `${safeArchiveBaseName}.zip`}`);
      log(`[info] Cause du fallback : ${nativeError?.message || String(nativeError)}`);
    }
  } catch (error) {
    setSidebarRuntimeStatus("Echec du telechargement", "error");
    setDownloadResultsStatus(`Téléchargement impossible : ${error?.message || String(error)}`, { isError: true });
    log(`[error] Téléchargement des résultats impossible : ${error?.message || String(error)}`);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = defaultLabel;
    }
    updateDownloadResultsState();
  }
}

function getChi2ChartFileName(term = "") {
  const corpusBaseName = getArchiveBaseName();
  const normalizedTerm = String(term || "").trim() || "forme";
  return `${corpusBaseName}_chi2_${normalizedTerm}_classes.png`;
}

function setTermSegmentsSaveStatus(message, { isError = false } = {}) {
  if (!termSegmentsStatus) return;
  termSegmentsStatus.textContent = message || "";
  termSegmentsStatus.classList.toggle("is-error", isError);
}

function setTermSegmentsExportState({ segments = [], filename = "", visible = false } = {}) {
  const cleanSegments = Array.isArray(segments)
    ? segments
        .map((segment) => String(segment || "").trim())
        .filter(Boolean)
    : [];

  appState.termSegmentsExport = visible
    ? {
        segments: cleanSegments,
        filename: String(filename || "").trim()
      }
    : null;

  if (termSegmentsFooter) {
    termSegmentsFooter.hidden = !visible && !appState.termChartExport?.visible;
  }

  if (buildSubcorpusBtn) {
    buildSubcorpusBtn.hidden = !visible;
    buildSubcorpusBtn.disabled = !visible || !cleanSegments.length;
  }

  setTermSegmentsSaveStatus("");
}

function setTermChartExportState({ visible = false, filename = "" } = {}) {
  appState.termChartExport = visible
    ? {
        visible: true,
        filename: String(filename || "").trim()
      }
    : null;

  if (saveChi2PngBtn) {
    saveChi2PngBtn.hidden = !visible;
    saveChi2PngBtn.disabled = !visible;
  }

  if (termSegmentsFooter) {
    termSegmentsFooter.hidden = !visible && !appState.termSegmentsExport;
  }

  setTermSegmentsSaveStatus("");
}

function buildSubcorpusContent(segments) {
  if (!Array.isArray(segments)) return "";
  return segments
    .map((segment) => String(segment || "").trim())
    .filter(Boolean)
    .join("\n\n");
}

function clearObjectUrls() {
  appState.objectUrls.forEach((url) => URL.revokeObjectURL(url));
  appState.objectUrls = [];
}

function clearContainer(container) {
  if (!(container instanceof HTMLElement)) {
    return false;
  }
  container.innerHTML = "";
  return true;
}

function setContainerEmptyState(container, message) {
  if (!clearContainer(container)) {
    return false;
  }
  container.appendChild(createEmptyState(message));
  return true;
}

function createObjectUrl(file) {
  const url = URL.createObjectURL(file);
  appState.objectUrls.push(url);
  return url;
}

function maybeCreateLocalFileUrl(path) {
  const safePath = String(path || "").trim();
  if (!safePath) return "";
  const convertFileSrc = window.__TAURI__?.core?.convertFileSrc;
  if (typeof convertFileSrc === "function") {
    try {
      return String(convertFileSrc(safePath) || "").trim();
    } catch (_error) {
      return "";
    }
  }
  if (safePath.startsWith("/")) {
    return `file://${encodeURI(safePath)}`;
  }
  return "";
}

function createEmptyState(message) {
  const wrapper = document.createElement("div");
  wrapper.className = "empty-state";
  wrapper.textContent = message;
  return wrapper;
}

function createDiagnosticState(message) {
  const wrapper = document.createElement("div");
  wrapper.className = "empty-state diagnostic-state";
  wrapper.textContent = message;
  return wrapper;
}

function getNavigationTargetForAnalysisKind({ isLdaMode = false, isSimiMode = false, isSuiviMode = false } = {}) {
  if (isLdaMode) return "lda";
  if (isSimiMode) return "similitudes";
  if (isSuiviMode) return "suivi_longitudinal";
  return "resultats_chd";
}

function renderAnalysisDiagnostic(message, navigationTarget = "resultats_chd") {
  const diagnosticText = String(message || "").trim() || "Aucun export exploitable n'a ete genere par l'analyse.";
  let containers = [];

  if (navigationTarget === "lda") {
    containers = [resultContainers.ldaBubblePlot, resultContainers.ldaHeatmap, resultContainers.ldaSegments];
  } else if (navigationTarget === "similitudes") {
    containers = [resultContainers.simiGraph];
  } else if (navigationTarget === "suivi_longitudinal") {
    containers = [resultContainers.suiviMeta, resultContainers.suiviIndicatorsTable, resultContainers.suiviEntropyPlot];
  } else {
    containers = [
      resultContainers.chdDendrogramme,
      resultContainers.chdStatsTable,
      resultContainers.chdConcordancier,
      resultContainers.chdWordclouds,
      resultContainers.afcClassesPlot,
      resultContainers.afcTermsPlot
    ];
  }

  containers.filter(Boolean).forEach((container) => {
    clearContainer(container);
    container.appendChild(createDiagnosticState(diagnosticText));
  });

  activateTopTab(navigationTarget);
  if (navigationTarget === "resultats_chd") {
    activateChdSubTab("dendrogramme");
  } else if (navigationTarget === "suivi_longitudinal") {
    activateSuiviSubTab("suivi_indicateurs");
  } else if (navigationTarget === "lda") {
    activateLdaSubTab("lda_bubble");
  }
}

function renderResults(files) {
  appState.exportEntries = files;
  updateDownloadResultsState();
  if (Array.isArray(files) && files.length > 0) {
    setDownloadResultsStatus("Les résultats sont prêts. Chaque analyse lancée peut être téléchargée depuis sa ligne.", {
      isError: false
    });
  }
}

function normalizeAnnotationApostrophes(value) {
  return String(value || "").replace(/[’`´ʼʹ]/g, "'");
}

function normalizeAnnotationSelectionValue(value) {
  return normalizeAnnotationApostrophes(String(value || "").trim().toLowerCase());
}

function buildAnnotationNormValue(value) {
  return normalizeAnnotationSelectionValue(value)
    .replace(/\s+/g, "_")
    .replace(/[^\p{L}\p{N}_]/gu, "");
}

function normalizeAnnotationMorphoValue(value) {
  const normalized = String(value || "").trim().toUpperCase();
  if (!normalized) {
    return "";
  }
  if (normalized === "AUTRE_FORME") {
    return "";
  }
  return ANNOTATION_MORPHO_CATEGORIES.includes(normalized) ? normalized : "";
}

function populateAnnotationMorphoOptions() {
  if (!(annotationMorpho instanceof HTMLSelectElement)) return;

  const currentValue = normalizeAnnotationMorphoValue(annotationMorpho.value);
  annotationMorpho.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choisir une catégorie (optionnel)";
  annotationMorpho.appendChild(placeholder);

  ANNOTATION_MORPHO_CATEGORIES.forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    annotationMorpho.appendChild(option);
  });

  annotationMorpho.value = currentValue;
}

function escapeAnnotationRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function sortAnnotationEntries(entries) {
  return [...entries].sort((left, right) => left.dic_mot.localeCompare(right.dic_mot, undefined, { sensitivity: "base" }));
}

function updateAnnotationSelectionFields(value) {
  const selectedText = String(value || "").trim();
  if (!selectedText) return;
  if (annotationSelection) annotationSelection.value = selectedText;
  if (annotationNorm) annotationNorm.value = buildAnnotationNormValue(selectedText);
}

function getAnnotationSelectionFromTextarea() {
  if (!(annotationCorpusText instanceof HTMLTextAreaElement)) return "";
  const start = annotationCorpusText.selectionStart ?? 0;
  const end = annotationCorpusText.selectionEnd ?? 0;
  if (end <= start) return "";
  return annotationCorpusText.value.slice(start, end).trim();
}

function renderAnnotationDictionaryTable() {
  if (!annotationDictTable) return;
  if (!appState.expressionAnnotations.length) {
    clearContainer(annotationDictTable);
    annotationDictTable.appendChild(createEmptyState("Aucune entrée annotée."));
    return;
  }

  renderTable(
    annotationDictTable,
    {
      headers: ["dic_mot", "dic_norm", "dic_morpho"],
      rows: appState.expressionAnnotations.map((entry) => [
        entry.dic_mot,
        entry.dic_norm,
        entry.dic_morpho || ""
      ])
    },
    {
      title: "Dictionnaire d'expressions (session)",
      maxRows: 300,
      onCellClick: ({ row }) => ({
        clickable: true,
        onClick: () => {
          fillAnnotationEditor({
            dic_mot: row[0],
            dic_norm: row[1],
            dic_morpho: row[2]
          });
          log(`[info] Entrée chargée dans l'éditeur : ${row[0]}`);
        }
      })
    }
  );
}

function renderAnnotationPreview() {
  if (!annotationCorpusColored) return;
  const text = annotationCorpusText?.value ?? appState.corpusText ?? "";

  clearContainer(annotationCorpusColored);

  if (!text.trim()) {
    annotationCorpusColored.textContent = "Aucun texte à annoter pour le moment.";
    return;
  }

  if (!appState.expressionAnnotations.length) {
    annotationCorpusColored.textContent = text;
    return;
  }

  const entries = sortAnnotationEntries(appState.expressionAnnotations)
    .map((entry) => entry.dic_mot)
    .filter(Boolean)
    .sort((left, right) => right.length - left.length);

  let html = escapeHtml(text);
  entries.forEach((entry) => {
    const normalized = normalizeAnnotationApostrophes(entry);
    const escaped = escapeAnnotationRegex(normalized).replace(/'/g, "['’`´ʼʹ]");
    const regex = new RegExp(`(?<![\\p{L}\\p{N}_])(${escaped})(?![\\p{L}\\p{N}_])`, "giu");
    html = html.replace(regex, "<span class=\"highlight\">$1</span>");
  });

  annotationCorpusColored.innerHTML = html;
}

function fillAnnotationEditor(entry = {}) {
  if (annotationSelection) annotationSelection.value = String(entry.dic_mot || "");
  if (annotationNorm) annotationNorm.value = String(entry.dic_norm || "");
  if (annotationMorpho) annotationMorpho.value = normalizeAnnotationMorphoValue(entry.dic_morpho);
  if (annotationRemoveKey) annotationRemoveKey.value = String(entry.dic_mot || "");
}

function setAnnotationSaveStatus(message, { isError = false } = {}) {
  if (!annotationSaveStatus) return;
  annotationSaveStatus.textContent = message;
  annotationSaveStatus.classList.toggle("is-error", isError);
}

function setAnnotationEntries(entries, { imported = false, persist = true } = {}) {
  const dedupedEntries = new Map();
  entries
    .map((entry) => ({
      dic_mot: normalizeAnnotationSelectionValue(entry.dic_mot),
      dic_norm: normalizeAnnotationSelectionValue(entry.dic_norm),
      dic_morpho: normalizeAnnotationMorphoValue(entry.dic_morpho)
    }))
    .filter((entry) => entry.dic_mot && entry.dic_norm)
    .forEach((entry) => {
      dedupedEntries.set(entry.dic_mot, entry);
    });

  appState.expressionAnnotations = sortAnnotationEntries([...dedupedEntries.values()]);

  renderAnnotationDictionaryTable();
  try {
    renderAnnotationPreview();
  } catch (error) {
    log(`[error] Prévisualisation d'annotation indisponible : ${error?.message || String(error)}`);
  }

  if (imported) {
    log(`[info] Dictionnaire d'annotation importé : ${appState.expressionAnnotations.length} entrée(s).`);
  }

  if (persist) {
    void persistAnnotationEntries();
  }
}

function parseAnnotationCsv(text) {
  const parsed = parseCsv(text);
  if (!parsed.headers.length) return [];

  const normalizedHeaders = parsed.headers.map((header) => String(header || "").trim().toLowerCase());
  const motIndex = normalizedHeaders.indexOf("dic_mot");
  const normIndex = normalizedHeaders.indexOf("dic_norm");
  const morphoIndex = normalizedHeaders.indexOf("dic_morpho");
  if (motIndex === -1 || normIndex === -1) {
    throw new Error("Colonnes attendues: dic_mot et dic_norm.");
  }

  return parsed.rows
    .map((row) => ({
      dic_mot: row[motIndex] || "",
      dic_norm: row[normIndex] || "",
      dic_morpho: morphoIndex === -1 ? "" : normalizeAnnotationMorphoValue(row[morphoIndex])
    }))
    .filter((entry) => String(entry.dic_mot || "").trim() && String(entry.dic_norm || "").trim());
}

function buildAnnotationCsvContent() {
  const rows = [["dic_mot", "dic_norm", "dic_morpho"]];
  appState.expressionAnnotations.forEach((entry) => {
    rows.push([entry.dic_mot, entry.dic_norm, entry.dic_morpho || ""]);
  });

  return rows
    .map((row) =>
      row
        .map((cell) => `"${String(cell || "").replaceAll("\"", "\"\"")}"`)
        .join(";")
    )
    .join("\n");
}

async function persistAnnotationEntries() {
  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) return;

  try {
    const payload = await tauriInvoke("write_annotation_dictionary_file", {
      content: buildAnnotationCsvContent()
    });
    log(`[info] Dictionnaire d'annotation sauvegardé : ${payload.entriesCount} entrée(s).`);
    setAnnotationSaveStatus(`Fichier enregistré dans Application Support : ${payload.path}`);
  } catch (error) {
    log(`[error] Sauvegarde du dictionnaire d'annotation impossible : ${error?.message || String(error)}`);
    setAnnotationSaveStatus(
      `Sauvegarde impossible : ${error?.message || String(error)}`,
      { isError: true }
    );
  }
}

async function resetAnnotationEntriesOnStartup() {
  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) return;

  try {
    const payload = await tauriInvoke("reset_annotation_dictionary_file");
    appState.expressionAnnotations = [];
    renderAnnotationDictionaryTable();
    renderAnnotationPreview();
    fillAnnotationEditor({});
    setAnnotationSaveStatus(`Le dictionnaire utilisateur sera enregistré ici : ${payload.path}`);
    if (payload?.removed) {
      log("[info] Dictionnaire utilisateur add_expression_fr.csv réinitialisé au démarrage.");
    }
  } catch (error) {
    log(`[error] Réinitialisation du dictionnaire d'annotation impossible : ${error?.message || String(error)}`);
    setAnnotationSaveStatus(
      `Initialisation du dictionnaire impossible : ${error?.message || String(error)}`,
      { isError: true }
    );
  }
}

function renderImage(container, file, altText, emptyMessage = "Aucun fichier image disponible.") {
  if (!clearContainer(container)) {
    return;
  }

  if (!file) {
    setContainerEmptyState(container, emptyMessage);
    return;
  }

  const image = document.createElement("img");
  image.className = "result-image";
  image.alt = altText;
  image.src = createObjectUrl(file);
  container.appendChild(image);
  if (container === resultContainers.afcTermsPlot) {
    applyAfcTermsZoom();
  }
  if (container === resultContainers.simiGraph) {
    applySimiZoom();
  }
}

function makeResultImagePreviewable(container, title, contextLabel) {
  const image = container?.querySelector(".result-image");
  if (!(image instanceof HTMLImageElement)) return;
  registerPreviewableImage(image, { title, kicker: contextLabel });
}

function renderImageGallery(container, items, emptyMessage, options = {}) {
  if (!clearContainer(container)) {
    return;
  }
  const { previewKicker = "" } = options;

  if (!items.length) {
    setContainerEmptyState(container, emptyMessage);
    return;
  }

  const gallery = document.createElement("div");
  gallery.className = "result-gallery";

  items.forEach(({ title, file }) => {
    const card = document.createElement("article");
    card.className = "result-gallery-item";

    const heading = document.createElement("h4");
    heading.textContent = title;
    card.appendChild(heading);

    const image = document.createElement("img");
    image.alt = title;
    image.src = createObjectUrl(file);
    if (previewKicker) {
      registerPreviewableImage(image, { title, kicker: previewKicker });
    }
    card.appendChild(image);

    gallery.appendChild(card);
  });

  container.appendChild(gallery);
}

function renderSelectableChdDendrogram() {
  const selectedValue = chdDendrogramSelect?.value || "iramuteq";
  const file = appState.chdDendrogramFiles.get(selectedValue) || null;
  const altText = selectedValue === "factoextra" ? "Dendrogramme CHD factoextra" : "Dendrogramme CHD IRaMuTeQ";
  syncDendrogramSizing();
  renderImage(resultContainers.chdDendrogramme, file, altText);
}

function openImagePreview(title, src, kicker = "Résultat", options = {}) {
  const fallbackItem = {
    title: String(title || "Image"),
    src: String(src || ""),
    kicker: String(kicker || "Résultat")
  };
  let items = Array.isArray(options?.items)
    ? options.items.filter((item) => String(item?.src || "").trim())
    : [];
  let index = Number.isFinite(options?.index) ? Number(options.index) : 0;

  if (!items.length && options?.sourceElement instanceof HTMLImageElement) {
    const collected = collectImagePreviewItems(options.sourceElement, fallbackItem);
    items = collected.items;
    index = collected.index >= 0 ? collected.index : 0;
  }

  if (!items.length && fallbackItem.src) {
    items = [fallbackItem];
    index = 0;
  }

  appState.imagePreviewItems = items;
  appState.imagePreviewIndex = Math.max(0, Math.min(items.length - 1, index));
  renderActiveImagePreview();
  if (imagePreviewDialog && !imagePreviewDialog.open) {
    if (typeof imagePreviewDialog.showModal === "function") {
      imagePreviewDialog.showModal();
    } else if (typeof imagePreviewDialog.show === "function") {
      imagePreviewDialog.show();
    }
  }
}

function closeImagePreview() {
  if (imagePreviewDialog?.open) {
    imagePreviewDialog.close();
  }
  appState.imagePreviewItems = [];
  appState.imagePreviewIndex = -1;
  if (imagePreviewContent) {
    imagePreviewContent.innerHTML = "";
  }
  updateImagePreviewNavigationState();
}

function formatNormalizedFaceSelection(box) {
  if (!box || !Array.isArray(box) || box.length !== 4) return "";
  const [x1, y1, x2, y2] = box.map((value) => Number(value || 0));
  return `rectangle gauche ${(x1 * 100).toFixed(1)}%, droite ${(x2 * 100).toFixed(1)}%, haut ${(y1 * 100).toFixed(1)}%, bas ${(y2 * 100).toFixed(1)}%`;
}

function formatFaceSelectionBoxArg(selection) {
  if (!selection || !Array.isArray(selection.box) || selection.box.length !== 4) {
    return "";
  }
  return selection.box.map((value) => Number(value || 0).toFixed(6)).join(",");
}

function formatFaceSelectionSourceNameArg(selection) {
  return String(selection?.sourceName || "").trim();
}

function formatFaceSelectionSourceIndexArg(selection) {
  const value = Number(selection?.sourceIndex);
  return Number.isInteger(value) && value >= 0 ? String(value) : "";
}

function getActiveMultimodalFaceSelectionSessionSources() {
  if (Array.isArray(multimodalFaceSelectionSession?.sources) && multimodalFaceSelectionSession.sources.length) {
    return multimodalFaceSelectionSession.sources;
  }
  return getSelectedMultimodalImageFiles().map((file, index) => ({
    name: file?.name || `Image ${index + 1}`,
    file,
    sourceName: file?.name || `Image ${index + 1}`,
    sourceIndex: index,
  }));
}

function getActiveMultimodalFaceSelectionSessionSelection() {
  if (multimodalFaceSelectionSession && multimodalFaceSelectionSession.selection) {
    return multimodalFaceSelectionSession.selection;
  }
  return appState.multimodalSelectedFaceSelection;
}

function resolveMultimodalFaceSelectionSourceItemUrl(sourceItem) {
  if (!sourceItem) return "";
  if (sourceItem.file instanceof File) {
    return createObjectUrl(sourceItem.file);
  }
  if (sourceItem.artifact) {
    return artifactDataToObjectUrl(sourceItem.artifact);
  }
  return maybeCreateLocalFileUrl(sourceItem.absolutePath || sourceItem.path || "");
}

function getMultimodalSelectedFaceSourceIndex() {
  const selection = appState.multimodalSelectedFaceSelection;
  const value = Number(selection?.sourceIndex);
  return Number.isInteger(value) && value >= 0 ? value : 0;
}

function getMultimodalSelectedFaceBoxArg() {
  return formatFaceSelectionBoxArg(appState.multimodalSelectedFaceSelection);
}

function getMultimodalSelectedFaceSourceNameArg() {
  return formatFaceSelectionSourceNameArg(appState.multimodalSelectedFaceSelection);
}

function getMultimodalSelectedFaceSourceIndexArg() {
  return formatFaceSelectionSourceIndexArg(appState.multimodalSelectedFaceSelection);
}

function clearMultimodalFaceSelection({ rerender = true } = {}) {
  appState.multimodalSelectedFaceSelection = null;
  multimodalFaceSelectionDraft = null;
  if (multimodalFaceSelectionCoords) {
    multimodalFaceSelectionCoords.textContent = "Aucune zone dessinée.";
  }
  if (rerender) {
    renderMultimodalWorkspace();
  }
}

function updateMultimodalFaceSelectionStatus() {
  if (!multimodalFaceSelectionStatus) return;
  const isBodyMode = multimodalMotionAnatomyMode?.value === "corps_entier";
  const isManualMode = multimodalMotionFaceAnalysisMode?.value === "manuel";
  const files = getSelectedMultimodalImageFiles();
  const sourceFile = files[0] || null;
  const selection = appState.multimodalSelectedFaceSelection;

  if (isBodyMode) {
    setReadonlyStatus(multimodalFaceSelectionStatus, "La sélection à la souris est disponible uniquement en mode visage.");
    return;
  }
  if (!sourceFile) {
    setReadonlyStatus(multimodalFaceSelectionStatus, "Importe d'abord une séquence d'images pour sélectionner un visage.");
    return;
  }
  if (!selection) {
    setReadonlyStatus(
      multimodalFaceSelectionStatus,
      isManualMode
        ? "Aucune sélection manuelle de visage. Clique sur « Sélectionner le visage à la souris »."
        : "Aucune sélection manuelle de visage."
    );
    return;
  }

  const sourceName = String(selection.sourceName || sourceFile.name || "image").trim();
  const sourceIndex = Number.isInteger(Number(selection.sourceIndex)) ? Number(selection.sourceIndex) : 0;
  setReadonlyStatus(
    multimodalFaceSelectionStatus,
    `Visage sélectionné sur ${sourceName} (image ${sourceIndex + 1}/${Math.max(1, files.length)}). Point de départ du suivi : ${formatNormalizedFaceSelection(selection.box)}.`
  );
}

function closeMultimodalFaceSelectionDialog() {
  if (multimodalFaceSelectionDialog?.open) {
    multimodalFaceSelectionDialog.close();
    return;
  }
  if (multimodalFaceSelectionStage) {
    multimodalFaceSelectionStage.innerHTML = "";
  }
  multimodalFaceSelectionSession = null;
}

function renderMultimodalFaceSelectionSurface(sourceItem) {
  if (!multimodalFaceSelectionStage) return;
  clearContainer(multimodalFaceSelectionStage);
  const activeSelection = getActiveMultimodalFaceSelectionSessionSelection();
  multimodalFaceSelectionDraft = Array.isArray(activeSelection?.box)
    ? [...activeSelection.box]
    : null;

  const imageSrc = resolveMultimodalFaceSelectionSourceItemUrl(sourceItem);
  if (!imageSrc) {
    multimodalFaceSelectionStage.appendChild(createEmptyState("Impossible d'afficher cette image de référence."));
    return;
  }
  const surface = document.createElement("div");
  surface.className = "multimodal-face-selection-surface";

  const image = document.createElement("img");
  image.src = imageSrc;
  image.alt = sourceItem?.name || sourceItem?.sourceName || "Image";
  surface.appendChild(image);

  const overlay = document.createElement("div");
  overlay.className = "multimodal-face-selection-overlay";
  surface.appendChild(overlay);

  const selectionBox = document.createElement("div");
  selectionBox.className = "multimodal-face-selection-box";
  overlay.appendChild(selectionBox);

  const applyDraft = () => {
    if (!multimodalFaceSelectionDraft) {
      selectionBox.hidden = true;
      if (multimodalFaceSelectionCoords) {
        multimodalFaceSelectionCoords.textContent = "Aucune zone dessinée.";
      }
      return;
    }
    const [x1, y1, x2, y2] = multimodalFaceSelectionDraft;
    selectionBox.hidden = false;
    selectionBox.style.left = `${x1 * 100}%`;
    selectionBox.style.top = `${y1 * 100}%`;
    selectionBox.style.width = `${(x2 - x1) * 100}%`;
    selectionBox.style.height = `${(y2 - y1) * 100}%`;
    if (multimodalFaceSelectionCoords) {
      multimodalFaceSelectionCoords.textContent = `Zone sélectionnée : ${formatNormalizedFaceSelection(multimodalFaceSelectionDraft)}`;
    }
  };

  let pointerId = null;
  let origin = null;
  const getNormalizedPoint = (event) => {
    const rect = overlay.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / Math.max(1, rect.width)));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / Math.max(1, rect.height)));
    return { x, y };
  };

  overlay.addEventListener("pointerdown", (event) => {
    pointerId = event.pointerId;
    origin = getNormalizedPoint(event);
    multimodalFaceSelectionDraft = [origin.x, origin.y, origin.x, origin.y];
    overlay.setPointerCapture(pointerId);
    applyDraft();
  });

  overlay.addEventListener("pointermove", (event) => {
    if (pointerId === null || !origin) return;
    const point = getNormalizedPoint(event);
    multimodalFaceSelectionDraft = [
      Math.min(origin.x, point.x),
      Math.min(origin.y, point.y),
      Math.max(origin.x, point.x),
      Math.max(origin.y, point.y),
    ];
    applyDraft();
  });

  const finishSelection = () => {
    if (!multimodalFaceSelectionDraft) return;
    const [x1, y1, x2, y2] = multimodalFaceSelectionDraft;
    if ((x2 - x1) < 0.01 || (y2 - y1) < 0.01) {
      multimodalFaceSelectionDraft = null;
    }
    pointerId = null;
    origin = null;
    applyDraft();
  };

  overlay.addEventListener("pointerup", () => {
    finishSelection();
  });
  overlay.addEventListener("pointercancel", () => {
    finishSelection();
  });

  multimodalFaceSelectionStage.appendChild(surface);
  applyDraft();
}

function renderMultimodalFaceSelectionSourceOptions(sourceItems) {
  if (!multimodalFaceSelectionSource) return;
  multimodalFaceSelectionSource.innerHTML = "";
  sourceItems.forEach((sourceItem, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${index + 1}. ${sourceItem?.name || sourceItem?.sourceName || `image_${index + 1}`}`;
    multimodalFaceSelectionSource.appendChild(option);
  });
  const activeSelection = getActiveMultimodalFaceSelectionSessionSelection();
  const safeIndex = Math.min(
    Math.max(0, Number(activeSelection?.sourceIndex) || 0),
    Math.max(0, sourceItems.length - 1),
  );
  multimodalFaceSelectionSource.value = String(safeIndex);
}

function openMultimodalFaceSelectionDialogSession(session) {
  const sourceItems = Array.isArray(session?.sources) ? session.sources : [];
  const safeIndex = Math.min(
    Math.max(0, Number(session?.selection?.sourceIndex) || 0),
    Math.max(0, sourceItems.length - 1),
  );
  const sourceItem = sourceItems[safeIndex] || null;
  if (!sourceItem) {
    setReadonlyStatus(
      multimodalFaceSelectionStatus,
      "Importe d'abord une séquence d'images avant de sélectionner un visage.",
      { isError: true }
    );
    return;
  }
  multimodalFaceSelectionSession = {
    sources: sourceItems,
    selection: session?.selection || null,
    onSave: typeof session?.onSave === "function" ? session.onSave : null,
    onClose: typeof session?.onClose === "function" ? session.onClose : null,
    handled: false,
  };
  renderMultimodalFaceSelectionSourceOptions(sourceItems);
  renderMultimodalFaceSelectionSurface(sourceItem);
  if (multimodalFaceSelectionDialog && !multimodalFaceSelectionDialog.open) {
    if (typeof multimodalFaceSelectionDialog.showModal === "function") {
      multimodalFaceSelectionDialog.showModal();
    } else if (typeof multimodalFaceSelectionDialog.show === "function") {
      multimodalFaceSelectionDialog.show();
    }
  }
}

function openMultimodalFaceSelectionDialog() {
  const files = getSelectedMultimodalImageFiles();
  const sources = files.map((file, index) => ({
    name: file?.name || `Image ${index + 1}`,
    file,
    sourceName: file?.name || `Image ${index + 1}`,
    sourceIndex: index,
  }));
  openMultimodalFaceSelectionDialogSession({
    sources,
    selection: appState.multimodalSelectedFaceSelection,
    onSave(selection) {
      appState.multimodalSelectedFaceSelection = selection;
      renderMultimodalWorkspace();
    },
    onClose() {
      renderMultimodalWorkspace();
    },
  });
}

function applySimiZoom() {
  if (simiZoomValue) {
    simiZoomValue.textContent = `${Math.round(appState.simiZoom * 100)}%`;
  }

  const media = resultContainers.simiGraph?.querySelector(".embedded-frame, .result-image");
  if (!(media instanceof HTMLElement)) return;

  media.style.width = `${Math.round(appState.simiZoom * 100)}%`;
  media.style.maxWidth = "none";
}

function setSimiZoom(nextZoom) {
  const zoom = Math.min(3, Math.max(0.4, Number(nextZoom) || 1));
  appState.simiZoom = zoom;
  applySimiZoom();
}

function applyAfcTermsZoom() {
  const container = resultContainers.afcTermsPlot;
  const media = resultContainers.afcTermsPlot?.querySelector(".result-image");
  if (!(media instanceof HTMLElement) || !(container instanceof HTMLElement)) return;

  const containerWidth = Math.max(0, Math.round(container.getBoundingClientRect().width || 0));
  const baseWidth = Math.max(320, Math.min(containerWidth || 800, 800));
  const targetWidth = Math.round(baseWidth * appState.afcTermsZoom);

  media.style.width = `${targetWidth}px`;
  media.style.maxWidth = "none";
  media.style.margin = "0 auto";
}

function setAfcTermsZoom(nextZoom) {
  const zoom = Math.min(3, Math.max(0.4, Number(nextZoom) || 1));
  appState.afcTermsZoom = zoom;
  applyAfcTermsZoom();
}

function openTermSegmentsDialog(classLabel, term) {
  const normalizedClass = normalizeClassValue(classLabel);
  const normalizedTerm = String(term || "").trim();
  const segments = (appState.chdSegmentsByClass.get(normalizedClass) || [])
    .filter((segment) => segmentContainsTerm(segment, normalizedTerm))
    .slice(0, 300);
  const filename = getSubcorpusFileName({
    term: normalizedTerm,
    classLabel: normalizedClass,
    scope: "classe"
  });

  if (termSegmentsKicker) {
    termSegmentsKicker.textContent = "Segments trouvés";
  }

  if (termSegmentsTitle) {
    termSegmentsTitle.textContent = `Classe ${normalizedClass} - forme: ${normalizedTerm}`;
  }

  if (termSegmentsMeta) {
    termSegmentsMeta.textContent = segments.length
      ? `Segments trouvés : ${segments.length}`
      : "Aucun segment trouvé pour cette forme dans la classe sélectionnée.";
  }

  if (termSegmentsList) {
    termSegmentsList.innerHTML = "";

    if (!appState.chdSegmentsByClass.size) {
      termSegmentsList.appendChild(
        createEmptyState("Le fichier segments_par_classe.txt est absent ou vide dans les exports.")
      );
    } else if (!segments.length) {
      termSegmentsList.appendChild(
        createEmptyState("Aucun segment trouvé pour cette forme dans la classe sélectionnée.")
      );
    } else {
      segments.forEach((segment) => {
        const paragraph = document.createElement("p");
        paragraph.className = "segment-popup-item";
        paragraph.innerHTML = highlightSegmentTerm(segment, normalizedTerm);
        termSegmentsList.appendChild(paragraph);
      });
    }
  }

  setTermSegmentsExportState({
    segments,
    filename,
    visible: true
  });

  if (termSegmentsDialog && !termSegmentsDialog.open) {
    if (typeof termSegmentsDialog.showModal === "function") {
      termSegmentsDialog.showModal();
    } else if (typeof termSegmentsDialog.show === "function") {
      termSegmentsDialog.show();
    }
  }
}

function closeTermSegmentsDialog() {
  setTermSegmentsExportState();
  setTermChartExportState();
  if (termSegmentsDialog?.open) {
    termSegmentsDialog.close();
  }
}

async function saveCurrentSubcorpus() {
  const exportState = appState.termSegmentsExport;
  const content = buildSubcorpusContent(exportState?.segments || []);
  if (!content) {
    setTermSegmentsSaveStatus("Aucun segment n'est disponible pour construire le sous-corpus.", { isError: true });
    return;
  }

  const filename = String(exportState?.filename || "sous-corpus.txt").trim() || "sous-corpus.txt";
  const tauriInvoke = getTauriInvoke();

  try {
    if (buildSubcorpusBtn) {
      buildSubcorpusBtn.disabled = true;
      buildSubcorpusBtn.textContent = "Préparation...";
    }

    setTermSegmentsSaveStatus("Construction du sous-corpus en cours...");

    if (tauriInvoke) {
      const payload = await tauriInvoke("save_text_export", {
        content,
        filename
      });
      const savedPath = payload.savedPath || payload.filename;
      setTermSegmentsSaveStatus(`Sous-corpus enregistré : ${savedPath}`);
      log(`[info] Sous-corpus enregistré : ${savedPath}`);
      await revealInFileManager(savedPath);
      return;
    }

    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setTermSegmentsSaveStatus(`Le navigateur a préparé ${filename}. Vérifie ton dossier Téléchargements.`);
  } catch (error) {
    const message = error?.message || String(error);
    setTermSegmentsSaveStatus(`Sous-corpus impossible à enregistrer : ${message}`, { isError: true });
    log(`[error] Construction du sous-corpus impossible : ${message}`);
  } finally {
    if (buildSubcorpusBtn) {
      buildSubcorpusBtn.disabled = !(appState.termSegmentsExport?.segments || []).length;
      buildSubcorpusBtn.textContent = "Construire un sous-corpus";
    }
  }
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = String(reader.result || "");
      const base64 = result.includes(",") ? result.split(",").pop() : "";
      if (!base64) {
        reject(new Error("Conversion base64 impossible."));
        return;
      }
      resolve(base64);
    };
    reader.onerror = () => {
      reject(reader.error || new Error("Lecture du blob impossible."));
    };
    reader.readAsDataURL(blob);
  });
}

async function buildChi2ChartPngBlob() {
  const svg = termSegmentsList?.querySelector(".chi2-comparison-chart");
  if (!(svg instanceof SVGElement)) {
    throw new Error("Le graphique χ² n'est pas disponible.");
  }

  const viewBox = svg.viewBox?.baseVal;
  const width = Math.max(400, Math.round(viewBox?.width || svg.clientWidth || 860));
  const height = Math.max(260, Math.round(viewBox?.height || svg.clientHeight || 360));
  const serializer = new XMLSerializer();
  const svgMarkup = serializer.serializeToString(svg);
  const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    const image = await new Promise((resolve, reject) => {
      const nextImage = new Image();
      nextImage.onload = () => resolve(nextImage);
      nextImage.onerror = () => reject(new Error("Chargement du graphique impossible."));
      nextImage.src = svgUrl;
    });

    const scale = 2;
    const canvas = document.createElement("canvas");
    canvas.width = width * scale;
    canvas.height = height * scale;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Canvas indisponible pour l'export PNG.");
    }

    context.fillStyle = "#fffaf7";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.scale(scale, scale);
    context.drawImage(image, 0, 0, width, height);

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob((result) => {
        if (result) {
          resolve(result);
          return;
        }
        reject(new Error("Création du PNG impossible."));
      }, "image/png");
    });

    return blob;
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}

async function saveCurrentChi2Chart() {
  const chartState = appState.termChartExport;
  if (!chartState?.visible) {
    setTermSegmentsSaveStatus("Aucun graphique χ² n'est disponible à enregistrer.", { isError: true });
    return;
  }

  const filename = String(chartState.filename || "chi2-classes.png").trim() || "chi2-classes.png";
  const tauriInvoke = getTauriInvoke();

  try {
    if (saveChi2PngBtn) {
      saveChi2PngBtn.disabled = true;
      saveChi2PngBtn.textContent = "Préparation...";
    }

    setTermSegmentsSaveStatus("Préparation du graphique χ² en PNG...");
    const pngBlob = await buildChi2ChartPngBlob();

    if (tauriInvoke) {
      const base64Data = await blobToBase64(pngBlob);
      const payload = await tauriInvoke("save_png_export", {
        data: base64Data,
        filename
      });
      const savedPath = payload.savedPath || payload.filename;
      setTermSegmentsSaveStatus(`Graphique enregistré : ${savedPath}`);
      log(`[info] Graphique χ² enregistré : ${savedPath}`);
      await revealInFileManager(savedPath);
      return;
    }

    const url = URL.createObjectURL(pngBlob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setTermSegmentsSaveStatus(`Le navigateur a préparé ${filename}. Vérifie ton dossier Téléchargements.`);
  } catch (error) {
    const message = error?.message || String(error);
    setTermSegmentsSaveStatus(`Enregistrement du graphique impossible : ${message}`, { isError: true });
    log(`[error] Enregistrement du graphique χ² impossible : ${message}`);
  } finally {
    if (saveChi2PngBtn) {
      saveChi2PngBtn.disabled = !appState.termChartExport?.visible;
      saveChi2PngBtn.textContent = "Enregistrer en PNG";
    }
  }
}

function openTermResultDialog({ kicker, title, meta, contentNode, subcorpus = null }) {
  if (termSegmentsKicker) {
    termSegmentsKicker.textContent = kicker || "Résultat CHD";
  }

  if (termSegmentsTitle) {
    termSegmentsTitle.textContent = title || "Action CHD";
  }

  if (termSegmentsMeta) {
    termSegmentsMeta.textContent = meta || "";
  }

  if (termSegmentsList) {
    termSegmentsList.innerHTML = "";
    if (contentNode) {
      termSegmentsList.appendChild(contentNode);
    } else {
      termSegmentsList.appendChild(createEmptyState("Aucun résultat disponible."));
    }
  }

  if (subcorpus && typeof subcorpus === "object") {
    setTermSegmentsExportState({
      segments: subcorpus.segments || [],
      filename: subcorpus.filename || "",
      visible: true
    });
  } else {
    setTermSegmentsExportState();
  }

  setTermChartExportState();

  if (termSegmentsDialog && !termSegmentsDialog.open) {
    if (typeof termSegmentsDialog.showModal === "function") {
      termSegmentsDialog.showModal();
    } else if (typeof termSegmentsDialog.show === "function") {
      termSegmentsDialog.show();
    }
  }
}

function openJsdConcordancierDialog(modeComparaison, uniteDepart, uniteArrivee, term) {
  const mode = String(modeComparaison || "").trim();
  const depart = String(uniteDepart || "").trim();
  const arrivee = String(uniteArrivee || "").trim();
  const terme = String(term || "").trim();

  const concordanceRows = (appState.jsdConcordancierRows || []).filter(
    (row) =>
      row.Mode_comparaison === mode &&
      row.Unite_depart === depart &&
      row.Unite_arrivee === arrivee &&
      row.Terme === terme
  );

  const content = document.createElement("div");
  const groupedRows = new Map();
  const orderedUnits = [depart, arrivee].filter(Boolean);
  const exportSegments = [];

  concordanceRows.forEach((row) => {
    const unit = row.Unite || "Entretien";
    if (!groupedRows.has(unit)) {
      groupedRows.set(unit, []);
    }
    groupedRows.get(unit).push(row);
  });

  groupedRows.forEach((_segments, unit) => {
    if (!orderedUnits.includes(unit)) {
      orderedUnits.push(unit);
    }
  });

  if (!concordanceRows.length) {
    content.appendChild(
      createEmptyState("Aucun segment contenant ce terme n'a été retrouvé dans le concordancier JSD.")
    );
  } else {
    orderedUnits.forEach((unit) => {
      const rows = groupedRows.get(unit) || [];
      if (!rows.length) return;

      const sectionTitle = document.createElement("h4");
      sectionTitle.className = "result-table-section-title";
      sectionTitle.textContent = unit;
      content.appendChild(sectionTitle);

      rows.forEach((row) => {
        const sourceSegment = String(row.Segment_source || row.Segment || "").trim();
        const lexicalSegment = String(row.Segment_lexical || "").trim();
        if (sourceSegment) {
          exportSegments.push(sourceSegment);
        } else if (lexicalSegment) {
          exportSegments.push(lexicalSegment);
        }

        const paragraph = document.createElement("p");
        paragraph.className = "segment-popup-item";
        const renderedBlocks = [];

        if (sourceSegment) {
          renderedBlocks.push(highlightSegmentTerm(sourceSegment, formatJsdDisplayedTerm(terme, false)));
        }

        if (lexicalSegment && lexicalSegment !== sourceSegment) {
          renderedBlocks.push(
            `<span class="muted"><strong>Vue lexicale :</strong> ${highlightSegmentTerm(
              lexicalSegment,
              formatJsdDisplayedTerm(terme, true)
            )}</span>`
          );
        }

        paragraph.innerHTML = renderedBlocks.filter(Boolean).join("<br>");
        content.appendChild(paragraph);
      });
    });
  }

  const unitsCount = new Set(concordanceRows.map((row) => row.Unite).filter(Boolean)).size;
  const modeLabel = humanizeSuiviComparisonMode(mode);
  openTermResultDialog({
    kicker: "Concordancier JSD",
    title: `${terme} · ${depart} → ${arrivee}`,
    meta: concordanceRows.length
      ? `${modeLabel} · ${concordanceRows.length} segment(s) · ${unitsCount} entretien(s)`
      : `${modeLabel} · concordancier indisponible`,
    contentNode: content,
    subcorpus: concordanceRows.length
      ? {
          segments: exportSegments,
          filename: getJsdConcordancierFileName({
            term: terme,
            uniteDepart: depart,
            uniteArrivee: arrivee,
            modeComparaison: mode
          })
        }
      : null
  });
}

function humanizeSuiviComparisonMode(value) {
  const raw = String(value || "").trim();
  if (!raw) return "Comparaison";

  const normalized = raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  const compact = normalized.replace(/\s+/g, "");

  if (normalized === "premiere seance" || compact === "premiereseance") {
    return "Première séance";
  }
  if (normalized === "seance precedente" || compact === "seanceprecedente") {
    return "Séance précédente";
  }

  return raw.replaceAll("_", " ");
}

function formatSuiviGalleryTitle(path, prefix) {
  const cleaned = String(path || "")
    .replace(/^.*\//, "")
    .replace(/\.png$/i, "")
    .replace(new RegExp(`^${prefix}__`), "");

  if (!cleaned) return "";

  const parts = cleaned.split("__vers__");
  if (parts.length !== 2) {
    return cleaned.replaceAll("_", " ");
  }

  const [leftPart, uniteArriveeRaw] = parts;
  const leftChunks = leftPart.split("__");
  if (leftChunks.length !== 2) {
    return cleaned.replaceAll("_", " ");
  }

  const [modeRaw, uniteDepartRaw] = leftChunks;
  const mode = humanizeSuiviComparisonMode(modeRaw);
  const uniteDepart = uniteDepartRaw.replaceAll("_", " ");
  const uniteArrivee = uniteArriveeRaw.replaceAll("_", " ");
  return `${mode} · ${uniteDepart} → ${uniteArrivee}`;
}

function formatActionNumber(value, { digits = 3 } = {}) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) return "N/A";
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(numeric);
}

function formatActionInteger(value) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) return "N/A";
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(numeric);
}

function buildSegmentsContent(segments, term) {
  if (!Array.isArray(segments) || !segments.length) {
    return createEmptyState("Aucun segment trouvé.");
  }

  const fragment = document.createDocumentFragment();
  segments.forEach((segment) => {
    const paragraph = document.createElement("p");
    paragraph.className = "segment-popup-item";
    paragraph.innerHTML = highlightSegmentTerm(segment, term);
    fragment.appendChild(paragraph);
  });
  return fragment;
}

function buildSegmentsByClassesContent(classes, term) {
  if (!Array.isArray(classes) || !classes.length) {
    return createEmptyState("Aucun segment trouvé dans les classes.");
  }

  const wrapper = document.createElement("div");
  wrapper.className = "segments-popup-list";

  classes.forEach((entry) => {
    const section = document.createElement("section");
    section.className = "term-action-group";

    const heading = document.createElement("h3");
    heading.textContent = `Classe ${normalizeClassValue(entry.classLabel)}`;
    section.appendChild(heading);

    const meta = document.createElement("p");
    meta.className = "term-action-group-meta";
    meta.textContent = `${formatActionInteger(entry.count)} segment(s)`;
    section.appendChild(meta);

    section.appendChild(buildSegmentsContent(entry.segments || [], term));
    wrapper.appendChild(section);
  });

  return wrapper;
}

function formatChi2AxisTick(value) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) return "";
  const abs = Math.abs(numeric);
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits
  }).format(numeric);
}

function getNiceAxisStep(range, targetTicks = 6) {
  const safeRange = Math.max(1, Number.parseFloat(range) || 1);
  const roughStep = safeRange / Math.max(2, targetTicks);
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const normalized = roughStep / magnitude;

  let multiplier = 10;
  if (normalized <= 1) multiplier = 1;
  else if (normalized <= 2) multiplier = 2;
  else if (normalized <= 5) multiplier = 5;

  return multiplier * magnitude;
}

function buildChi2Content(payload) {
  const classes = Array.isArray(payload?.classes) ? payload.classes : [];
  if (!classes.length) {
    return createEmptyState("Aucune valeur de χ² disponible pour cette forme.");
  }

  const wrapper = document.createElement("div");
  wrapper.className = "term-action-group";

  const chartWidth = 920;
  const chartHeight = 360;
  const values = classes.map((entry) => Number.parseFloat(entry?.chi2)).filter(Number.isFinite);
  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  const yMax = maxAbs * 1.12;
  const gridValues = [];
  const gridStep = getNiceAxisStep(yMax * 2, 6);
  for (let current = -Math.ceil(yMax / gridStep) * gridStep; current <= yMax + gridStep * 0.5; current += gridStep) {
    gridValues.push(current);
  }
  if (!gridValues.some((tick) => Math.abs(tick) < 1e-9)) {
    gridValues.push(0);
    gridValues.sort((left, right) => left - right);
  }

  const longestTickLabel = Math.max(...gridValues.map((tick) => formatChi2AxisTick(tick).length), 1);
  const margin = {
    top: 18,
    right: 28,
    bottom: 92,
    left: Math.max(76, 18 + longestTickLabel * 8)
  };
  const plotWidth = chartWidth - margin.left - margin.right;
  const plotHeight = chartHeight - margin.top - margin.bottom;
  const zeroY = margin.top + plotHeight * 0.5;
  const barSlot = plotWidth / Math.max(classes.length, 1);
  const barWidth = Math.min(60, Math.max(22, barSlot * 0.56));

  const yToPx = (value) => margin.top + ((yMax - value) / (2 * yMax)) * plotHeight;

  const svgParts = [
    `<svg viewBox="0 0 ${chartWidth} ${chartHeight}" class="chi2-comparison-chart" role="img" aria-label="χ² par classe pour la forme sélectionnée">`,
    `<rect x="0" y="0" width="${chartWidth}" height="${chartHeight}" fill="#fffaf7" rx="18" ry="18"></rect>`
  ];

  gridValues.forEach((tick) => {
    const y = yToPx(tick);
    const isZero = Math.abs(tick) < 1e-9;
    svgParts.push(
      `<line x1="${margin.left}" y1="${y}" x2="${chartWidth - margin.right}" y2="${y}" stroke="${isZero ? "#3b302c" : "#d9cfc8"}" stroke-width="${isZero ? 1.6 : 1}" stroke-dasharray="${isZero ? "" : "4 5"}"></line>`
    );
    svgParts.push(
      `<text x="${margin.left - 10}" y="${y + 4}" text-anchor="end" font-size="11" fill="#6f625b">${escapeHtml(formatChi2AxisTick(tick))}</text>`
    );
  });

  classes.forEach((entry, index) => {
    const value = Number.parseFloat(entry?.chi2);
    const safeValue = Number.isFinite(value) ? value : 0;
    const centerX = margin.left + index * barSlot + barSlot / 2;
    const y = yToPx(safeValue);
    const rectY = safeValue >= 0 ? y : zeroY;
    const rectHeight = Math.max(2, Math.abs(zeroY - y));
    const fill = entry?.isSelected ? "#c72318" : "#ef3b2d";
    const stroke = entry?.isSelected ? "#4b110d" : "#6b2019";
    const label = escapeHtml(`Classe ${normalizeClassValue(entry?.classLabel)}`);

    svgParts.push(
      `<rect x="${centerX - barWidth / 2}" y="${rectY}" width="${barWidth}" height="${rectHeight}" fill="${fill}" stroke="${stroke}" stroke-width="1.6" rx="2" ry="2"></rect>`
    );
    svgParts.push(
      `<text x="${centerX}" y="${chartHeight - 16}" text-anchor="end" transform="rotate(-65 ${centerX} ${chartHeight - 16})" font-size="11" fill="#2e2723">${label}</text>`
    );
  });

  svgParts.push(`</svg>`);

  const chart = document.createElement("div");
  chart.className = "chi2-comparison-chart-wrap";
  chart.innerHTML = svgParts.join("");
  wrapper.appendChild(chart);

  const selectedClassLabel = payload?.selectedClassLabel ? `Classe ${normalizeClassValue(payload.selectedClassLabel)}` : "Classe sélectionnée";
  const stats = [
    ["Classe", selectedClassLabel],
    ["χ²", formatActionNumber(payload?.selectedChi2)],
    ["p.value", formatActionNumber(payload?.selectedPValue, { digits: 6 })],
    ["Type", payload?.type || "N/A"]
  ];

  const grid = document.createElement("dl");
  grid.className = "term-stats-grid";

  stats.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "term-stat-card";

    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;

    card.append(dt, dd);
    grid.appendChild(card);
  });

  wrapper.appendChild(grid);
  return wrapper;
}

function renderChdActionResult(result) {
  const action = String(result?.action || "");
  const term = String(result?.term || "").trim();
  const title = result?.title || "Action CHD";
  const meta = result?.meta || "";

  if (action === "chi2-class") {
    openTermResultDialog({
      kicker: "χ² par classe",
      title,
      meta,
      contentNode: buildChi2Content(result.payload || {})
    });
    setTermChartExportState({
      visible: true,
      filename: getChi2ChartFileName(term)
    });
    return;
  }

  if (action === "segments-all-classes") {
    const classes = result?.payload?.classes || [];
    const segments = classes.flatMap((entry) =>
      Array.isArray(entry?.segments) ? entry.segments.map((segment) => String(segment || "")) : []
    );
    openTermResultDialog({
      kicker: "Segments dans les classes",
      title,
      meta,
      contentNode: buildSegmentsByClassesContent(classes, term),
      subcorpus: {
        segments,
        filename: getSubcorpusFileName({
          term,
          scope: "classes"
        })
      }
    });
    return;
  }

  const segments = Array.isArray(result?.payload?.segments) ? result.payload.segments : [];
  openTermResultDialog({
    kicker: "Segments trouvés",
    title,
    meta,
    contentNode: buildSegmentsContent(segments, term),
    subcorpus: {
      segments,
      filename: getSubcorpusFileName({
        term,
        classLabel: result?.payload?.classLabel || result?.classLabel || "",
        scope: "classe"
      })
    }
  });
}

function closeChdTermContextMenu() {
  appState.chdContextMenu = null;
  if (!chdTermContextMenu) return;
  chdTermContextMenu.hidden = true;
  chdTermContextMenu.style.left = "";
  chdTermContextMenu.style.top = "";
  chdTermContextMenu.style.visibility = "";
}

function openChdTermContextMenu({ event, term, classLabel }) {
  if (!chdTermContextMenu) return;

  event.preventDefault();
  event.stopPropagation();

  const normalizedClass = normalizeClassValue(classLabel);
  const normalizedTerm = String(term || "").trim();
  if (!normalizedTerm) return;

  appState.chdContextMenu = {
    term: normalizedTerm,
    classLabel: normalizedClass
  };

  chdTermContextMenu.hidden = false;
  chdTermContextMenu.style.left = "0px";
  chdTermContextMenu.style.top = "0px";
  chdTermContextMenu.style.visibility = "hidden";

  const menuRect = chdTermContextMenu.getBoundingClientRect();
  const left = Math.max(10, Math.min(event.clientX, window.innerWidth - menuRect.width - 10));
  const top = Math.max(10, Math.min(event.clientY, window.innerHeight - menuRect.height - 10));

  chdTermContextMenu.style.left = `${left}px`;
  chdTermContextMenu.style.top = `${top}px`;
  chdTermContextMenu.style.visibility = "visible";
}

async function invokeChdAction(action) {
  const current = appState.chdContextMenu;
  closeChdTermContextMenu();

  if (!current?.term || !appState.outputDir) {
    log("[error] Action CHD impossible : aucune forme ou aucun dossier d'exports disponible.");
    return;
  }

  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    log("[error] Les actions CHD au clic droit sont disponibles uniquement dans l'application Tauri.");
    return;
  }

  try {
    log(`[info] Action CHD : ${action} pour la forme ${current.term}.`);
    const result = await tauriInvoke("run_chd_action", {
      outputDir: appState.outputDir,
      action,
      term: current.term,
      classLabel: current.classLabel
    });
    if (Array.isArray(result?.logs)) {
      result.logs.forEach((line) => {
        if (line) log(`[info] ${line}`);
      });
    }
    renderChdActionResult(result);
  } catch (error) {
    log(`[error] Action CHD impossible : ${error?.message || String(error)}`);
  }
}

function createEmbeddedFrame(htmlText, className = "embedded-frame") {
  const iframe = document.createElement("iframe");
  iframe.className = className;
  iframe.srcdoc = htmlText;
  return iframe;
}

function getConcordancierInjectedStyle() {
  return `
<style>
  h1, h2, h3 {
    line-height: 1.08 !important;
    letter-spacing: 0;
  }
  h1 {
    font-size: 1rem !important;
    margin: 0 0 0.18rem !important;
  }
  h2 {
    font-size: 0.9rem !important;
    margin: 0 0 0.14rem !important;
  }
  h3 {
    font-size: 0.78rem !important;
    margin: 0 0 0.3rem !important;
    font-weight: 500 !important;
  }
  h2.classe-heading,
  .classe-heading {
    font-size: 1.8rem !important;
    line-height: 1.02 !important;
    color: #b42318 !important;
    font-weight: 700 !important;
    margin: 0 0 0.42rem !important;
  }
</style>`;
}

function buildConcordancierHtmlDocument(headHtml, bodyHtml) {
  return `<!DOCTYPE html><html><head>${headHtml || ""}${getConcordancierInjectedStyle()}</head><body>${bodyHtml || ""}</body></html>`;
}

function renderConcordancierFrame(container, htmlText, emptyMessage) {
  if (!clearContainer(container)) {
    return;
  }

  if (!htmlText) {
    setContainerEmptyState(container, emptyMessage);
    return;
  }

  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlText, "text/html");
    const classBlocks = Array.from(doc.querySelectorAll(".classe-bloc"));

    if (!classBlocks.length) {
      container.appendChild(createEmbeddedFrame(buildConcordancierHtmlDocument(doc.head?.innerHTML || "", doc.body?.innerHTML || htmlText)));
      return;
    }

    const bodyChildren = Array.from(doc.body?.children || []);
    const firstBlock = classBlocks[0];
    const commonHeaderHtml = bodyChildren
      .slice(0, Math.max(0, bodyChildren.indexOf(firstBlock)))
      .map((node) => node.outerHTML)
      .join("");

    const tabs = document.createElement("div");
    tabs.className = "concordancier-class-tabs";

    const panels = document.createElement("div");
    panels.className = "concordancier-class-panels";

    const activateClassTab = (activeIndex) => {
      tabs.querySelectorAll(".concordancier-class-tab").forEach((button, index) => {
        button.classList.toggle("is-active", index === activeIndex);
      });
      panels.querySelectorAll(".concordancier-class-panel").forEach((panel, index) => {
        panel.hidden = index !== activeIndex;
        panel.classList.toggle("is-active", index === activeIndex);
      });
    };

    classBlocks.forEach((block, index) => {
      const heading = block.querySelector(".classe-heading, h2");
      const classLabel = String(heading?.textContent || `Classe ${index + 1}`).trim();

      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button concordancier-class-tab";
      button.textContent = `Concor ${classLabel}`;
      button.addEventListener("click", () => activateClassTab(index));
      tabs.appendChild(button);

      const panel = document.createElement("div");
      panel.className = "concordancier-class-panel";
      panel.hidden = index !== 0;
      panel.appendChild(
        createEmbeddedFrame(
          buildConcordancierHtmlDocument(
            doc.head?.innerHTML || "",
            `${commonHeaderHtml}${block.outerHTML}`
          ),
          "embedded-frame embedded-frame--concordancier"
        )
      );
      panels.appendChild(panel);
    });

    container.appendChild(tabs);
    container.appendChild(panels);
    activateClassTab(0);
  } catch (error) {
    log(`[error] Découpage du concordancier par classe impossible : ${error?.message || String(error)}`);
    container.appendChild(createEmbeddedFrame(`${getConcordancierInjectedStyle()}${htmlText}`));
  }
}

function renderHtmlFrame(container, htmlText, emptyMessage) {
  if (container === resultContainers.chdConcordancier) {
    renderConcordancierFrame(container, htmlText, emptyMessage);
    return;
  }

  if (!clearContainer(container)) {
    return;
  }

  if (!htmlText) {
    setContainerEmptyState(container, emptyMessage);
    return;
  }

  const iframe = createEmbeddedFrame(htmlText);
  container.appendChild(iframe);
  if (container === resultContainers.simiGraph) {
    applySimiZoom();
  }
}

function detectDelimiter(text) {
  const firstLine = text.split(/\r?\n/, 1)[0] || "";
  const commaCount = (firstLine.match(/,/g) || []).length;
  const semicolonCount = (firstLine.match(/;/g) || []).length;
  return semicolonCount > commaCount ? ";" : ",";
}

function parseDelimited(text, delimiter) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];

    if (character === "\"") {
      if (inQuotes && text[index + 1] === "\"") {
        field += "\"";
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (character === delimiter && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }

    if ((character === "\n" || character === "\r") && !inQuotes) {
      if (character === "\r" && text[index + 1] === "\n") {
        index += 1;
      }

      row.push(field);
      if (row.some((cell) => cell.length > 0)) {
        rows.push(row);
      }
      row = [];
      field = "";
      continue;
    }

    field += character;
  }

  row.push(field);
  if (row.some((cell) => cell.length > 0)) {
    rows.push(row);
  }

  return rows;
}

function parseCsv(text) {
  const delimiter = detectDelimiter(text);
  const rows = parseDelimited(text, delimiter);

  if (!rows.length) {
    return { headers: [], rows: [] };
  }

  const headers = rows[0].map((cell, index) => {
    const value = String(cell ?? "");
    return index === 0 ? value.replace(/^\ufeff/, "") : value;
  });
  const body = rows.slice(1).map((row) => {
    const normalizedRow = [...row];
    while (normalizedRow.length < headers.length) {
      normalizedRow.push("");
    }
    return normalizedRow.slice(0, headers.length);
  });

  return { headers, rows: body };
}

function rowsFromParsedCsv(parsed) {
  if (!parsed?.headers?.length || !Array.isArray(parsed.rows)) {
    return [];
  }

  return parsed.rows.map((row) =>
    Object.fromEntries(parsed.headers.map((header, index) => [header, row[index] ?? ""]))
  );
}

function parseJsdConcordancierRows(parsed) {
  return rowsFromParsedCsv(parsed)
    .map((row) => ({
      Mode_comparaison: String(row.Mode_comparaison || "").trim(),
      Unite_depart: String(row.Unite_depart || "").trim(),
      Unite_arrivee: String(row.Unite_arrivee || "").trim(),
      Unite: String(row.Unite || "").trim(),
      Terme: String(row.Terme || "").trim(),
      Segment: String(row.Segment || "").trim(),
      Segment_source: String(row.Segment_source || "").trim(),
      Segment_lexical: String(row.Segment_lexical || "").trim()
    }))
    .filter((row) => row.Terme && (row.Segment || row.Segment_source || row.Segment_lexical));
}

function normalizeClassValue(rawValue) {
  const raw = String(rawValue || "").trim();
  if (!raw) return "Sans classe";
  const stripped = raw.replace(/^classe\s+/i, "").replace(/:$/, "").trim() || raw;
  const numeric = Number.parseFloat(stripped.replace(",", "."));
  if (Number.isFinite(numeric)) {
    return String(Number.isInteger(numeric) ? numeric : numeric);
  }
  return stripped;
}

function parseSegmentsByClassText(text) {
  const groups = new Map();
  let currentClass = null;

  String(text || "").split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    const headerMatch = trimmed.match(/^Classe\s+(.+?)\s*:\s*$/i);
    if (headerMatch) {
      currentClass = normalizeClassValue(headerMatch[1]);
      if (!groups.has(currentClass)) groups.set(currentClass, []);
      return;
    }
    if (!currentClass || !trimmed) return;
    groups.get(currentClass).push(trimmed);
  });

  return groups;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildLooseTermRegex(term, flags = "iu") {
  return new RegExp(`(^|[^\\p{L}\\p{N}_])(${escapeRegex(term)})($|[^\\p{L}\\p{N}_])`, flags);
}

function segmentContainsTerm(segment, term) {
  return buildLooseTermRegex(term).test(String(segment || ""));
}

function highlightSegmentTerm(segment, term) {
  const regex = buildLooseTermRegex(term, "giu");
  return String(segment || "").replace(
    regex,
    (_match, prefix, core, suffix) => `${escapeHtml(prefix)}<mark>${escapeHtml(core)}</mark>${escapeHtml(suffix)}`
  );
}

function formatJsdDisplayedTerm(term, lexical = false) {
  const raw = String(term || "").trim();
  if (!raw) return "";
  return lexical ? raw.replaceAll("_", " ") : raw;
}

function buildLdaTopicTermLookup(parsed, maxTermsPerTopic = 20) {
  const topicGroups = parseLdaTopicGroups(parsed);
  if (!topicGroups?.topics?.length) return new Map();

  const lookup = new Map();
  topicGroups.topics.forEach((topic) => {
    const canonicalTopic = canonicalizeTopicLabel(topic);
    let entries = (topicGroups.topicMap.get(topic) || [])
      .filter((entry) => entry && entry.term && Number.isFinite(entry.prob) && entry.prob > 0);
    if (Number.isFinite(maxTermsPerTopic) && maxTermsPerTopic > 0) {
      entries = entries.slice(0, maxTermsPerTopic);
    }
    const terms = entries
      .map((entry) => String(entry.term).trim())
      .filter(Boolean);
    lookup.set(canonicalTopic, terms);
  });

  return lookup;
}

function highlightLdaSegmentTerms(segment, terms) {
  const source = String(segment || "");
  const termList = [...new Set((terms || []).map((term) => String(term || "").trim()).filter(Boolean))]
    .sort((left, right) => right.length - left.length);

  if (!source || !termList.length) {
    return escapeHtml(source);
  }

  const matches = [];
  const overlaps = (start, end) => matches.some((item) => start < item.end && end > item.start);
  const collectTermMatches = (term) => {
    const regex = buildLooseTermRegex(term, "giu");
    let found = false;
    let match;
    while ((match = regex.exec(source)) !== null) {
      const prefix = match[1] || "";
      const core = match[2] || "";
      if (!core) continue;
      const start = match.index + prefix.length;
      const end = start + core.length;
      if (overlaps(start, end)) continue;
      matches.push({ start, end });
      found = true;
    }
    return found;
  };

  termList.forEach((term) => {
    const foundExact = collectTermMatches(term);
    if (!foundExact && term.includes(" ")) {
      const parts = term
        .split(/\s+/)
        .map((part) => part.trim())
        .filter((part) => part.length >= 3);
      parts.forEach((part) => {
        collectTermMatches(part);
      });
    }
  });

  if (!matches.length) {
    return escapeHtml(source);
  }

  matches.sort((left, right) => left.start - right.start);
  let cursor = 0;
  let html = "";
  matches.forEach((match) => {
    html += escapeHtml(source.slice(cursor, match.start));
    html += `<mark class="lda-segment-mark">${escapeHtml(source.slice(match.start, match.end))}</mark>`;
    cursor = match.end;
  });
  html += escapeHtml(source.slice(cursor));
  return html;
}

function renderTable(container, parsed, options = {}) {
  if (!clearContainer(container)) {
    return;
  }

  if (!parsed || !parsed.headers.length) {
    setContainerEmptyState(container, options.emptyMessage || "Aucun tableau disponible.");
    return;
  }

  const title = options.title || null;
  const maxRows = Number.isFinite(options.maxRows) ? options.maxRows : 80;
  const visibleRows = parsed.rows.slice(0, maxRows);
  const onCellClick = typeof options.onCellClick === "function" ? options.onCellClick : null;
  const rowClassName = typeof options.rowClassName === "function" ? options.rowClassName : null;
  const cellClassName = typeof options.cellClassName === "function" ? options.cellClassName : null;
  const cellRenderer = typeof options.cellRenderer === "function" ? options.cellRenderer : null;

  if (title) {
    const caption = document.createElement("p");
    caption.className = "result-table-caption";
    caption.textContent =
      parsed.rows.length > maxRows
        ? `${title} · ${visibleRows.length} lignes affichées sur ${parsed.rows.length}`
        : `${title} · ${parsed.rows.length} lignes`;
    container.appendChild(caption);
  }

  const wrap = document.createElement("div");
  wrap.className = "result-table-wrap";

  const table = document.createElement("table");
  table.className = "result-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  parsed.headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header || " ";
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  visibleRows.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");
    if (rowClassName) {
      const className = rowClassName({ row, rowIndex, headers: parsed.headers });
      if (className) {
        String(className)
          .split(/\s+/)
          .filter(Boolean)
          .forEach((name) => tr.classList.add(name));
      }
    }
    row.forEach((cell, columnIndex) => {
      const td = document.createElement("td");
      const payload = { cell, row, rowIndex, columnIndex, headers: parsed.headers };
      const renderedCell = cellRenderer ? cellRenderer(payload) : null;
      if (cellClassName) {
        const className = cellClassName(payload);
        if (className) {
          String(className)
            .split(/\s+/)
            .filter(Boolean)
            .forEach((name) => td.classList.add(name));
        }
      }
      if (renderedCell?.className) {
        String(renderedCell.className)
          .split(/\s+/)
          .filter(Boolean)
          .forEach((name) => td.classList.add(name));
      }
      if (onCellClick) {
        const clickPayload = payload;
        const cellOptions = onCellClick(clickPayload);
        if (cellOptions?.clickable) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "cell-button";
          if (cellOptions.className) {
            String(cellOptions.className)
              .split(/\s+/)
              .filter(Boolean)
              .forEach((name) => button.classList.add(name));
          }
          if (renderedCell?.html !== undefined) {
            button.innerHTML = renderedCell.html;
          } else {
            button.textContent = renderedCell?.text ?? cell;
          }
          button.addEventListener("click", () => cellOptions.onClick?.(clickPayload));
          if (typeof cellOptions.onContextMenu === "function") {
            button.addEventListener("contextmenu", (event) => {
              cellOptions.onContextMenu?.(event, clickPayload);
            });
          }
          td.appendChild(button);
        } else {
          if (renderedCell?.html !== undefined) {
            td.innerHTML = renderedCell.html;
          } else {
            td.textContent = renderedCell?.text ?? cell;
          }
        }
      } else {
        if (renderedCell?.html !== undefined) {
          td.innerHTML = renderedCell.html;
        } else {
          td.textContent = renderedCell?.text ?? cell;
        }
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  container.appendChild(wrap);
}

function omitParsedColumns(parsed, headersToOmit = []) {
  if (!parsed || !Array.isArray(parsed.headers) || !Array.isArray(parsed.rows)) {
    return parsed;
  }

  const omitSet = new Set(headersToOmit.map((header) => String(header || "")));
  const keptIndexes = parsed.headers
    .map((header, index) => ({ header, index }))
    .filter(({ header }) => !omitSet.has(String(header || "")));

  return {
    headers: keptIndexes.map(({ header }) => header),
    rows: parsed.rows.map((row) => keptIndexes.map(({ index }) => row[index])),
  };
}

function formatSummaryValue(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  if (typeof value === "number") return new Intl.NumberFormat("fr-FR").format(value);
  return String(value);
}

function renderAnalysisSteps(logLines) {
  clearContainer(analysisSteps);

  if (!Array.isArray(logLines) || !logLines.length) {
    analysisSteps.appendChild(createEmptyState("Les étapes s'afficheront après le lancement d'une analyse."));
    return;
  }

  const list = document.createElement("ol");
  list.className = "steps-list";

  logLines.forEach((line) => {
    const item = document.createElement("li");
    item.textContent = String(line).replace(/^\[[^\]]+\]\s*/, "").trim() || String(line);
    list.appendChild(item);
  });

  analysisSteps.appendChild(list);
}

function renderAnalysisSummary(summary) {
  clearContainer(analysisSummary);

  if (!summary || typeof summary !== "object" || !Object.keys(summary).length) {
    analysisSummary.appendChild(createEmptyState("La synthèse du corpus apparaîtra après l'analyse."));
    return;
  }

  const metrics = [
    ["Corpus", summary.corpus],
    ["Nombre de textes", summary.n_texts],
    ["Nombre de segments", summary.n_segments],
    ["Nombre d'occurrences", summary.n_tokens],
    ["Nombre de formes", summary.n_formes],
    ["Nombre d'hapax", summary.n_hapax],
    ["Nombre de classes", summary.n_classes]
  ];

  const grid = document.createElement("div");
  grid.className = "summary-grid";

  metrics.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "summary-card";

    const title = document.createElement("p");
    title.className = "summary-label";
    title.textContent = label;

    const body = document.createElement("strong");
    body.className = "summary-value";
    body.textContent = formatSummaryValue(value);

    card.appendChild(title);
    card.appendChild(body);
    grid.appendChild(card);
  });

  analysisSummary.appendChild(grid);
}

function renderZipfChart(summary) {
  clearContainer(zipfChart);

  const zipf = Array.isArray(summary?.zipf) ? summary.zipf : [];
  if (!zipf.length) {
    zipfChart.appendChild(createEmptyState("Le graphique Zipf sera disponible après l'analyse."));
    return;
  }

  const width = 1000;
  const height = 1000;
  const padding = 84;
  const points = zipf
    .map((item) => ({
      x: Number(item.log_rang),
      y: Number(item.log_frequence),
      pred: Number(item.log_pred)
    }))
    .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));

  if (points.length < 2) {
    zipfChart.appendChild(createEmptyState("Pas assez de points pour tracer la loi de Zipf."));
    return;
  }

  const maxX = Math.max(...points.map((item) => item.x));
  const maxY = Math.max(...points.map((item) => item.y));
  const minX = Math.min(...points.map((item) => item.x));
  const minY = Math.min(...points.map((item) => item.y));
  const scaleX = (value) =>
    padding + ((value - minX) / Math.max(1e-9, maxX - minX)) * (width - padding * 2);
  const scaleY = (value) =>
    height - padding - ((value - minY) / Math.max(1e-9, maxY - minY)) * (height - padding * 2);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "zipf-svg");

  const plotLeft = padding;
  const plotRight = width - padding;
  const plotTop = padding;
  const plotBottom = height - padding;
  const gridSteps = 5;

  for (let index = 0; index <= gridSteps; index += 1) {
    const x = plotLeft + ((plotRight - plotLeft) / gridSteps) * index;
    const y = plotTop + ((plotBottom - plotTop) / gridSteps) * index;

    const vGrid = document.createElementNS("http://www.w3.org/2000/svg", "line");
    vGrid.setAttribute("x1", String(x));
    vGrid.setAttribute("y1", String(plotTop));
    vGrid.setAttribute("x2", String(x));
    vGrid.setAttribute("y2", String(plotBottom));
    vGrid.setAttribute("stroke", "#E6E6E6");
    vGrid.setAttribute("stroke-width", "1");
    vGrid.setAttribute("stroke-dasharray", "2 6");
    svg.appendChild(vGrid);

    const hGrid = document.createElementNS("http://www.w3.org/2000/svg", "line");
    hGrid.setAttribute("x1", String(plotLeft));
    hGrid.setAttribute("y1", String(y));
    hGrid.setAttribute("x2", String(plotRight));
    hGrid.setAttribute("y2", String(y));
    hGrid.setAttribute("stroke", "#E6E6E6");
    hGrid.setAttribute("stroke-width", "1");
    hGrid.setAttribute("stroke-dasharray", "2 6");
    svg.appendChild(hGrid);
  }

  const axes = [
    { x1: padding, y1: height - padding, x2: width - padding, y2: height - padding },
    { x1: padding, y1: padding, x2: padding, y2: height - padding }
  ];

  axes.forEach((axis) => {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    Object.entries(axis).forEach(([key, value]) => line.setAttribute(key, String(value)));
    line.setAttribute("stroke", "#8d867d");
    line.setAttribute("stroke-width", "1.5");
    svg.appendChild(line);
  });

  points.forEach((item) => {
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", String(scaleX(item.x)));
    dot.setAttribute("cy", String(scaleY(item.y)));
    dot.setAttribute("r", "4.6");
    dot.setAttribute("fill", "#2C7FB8");
    dot.setAttribute("fill-opacity", "0.7");
    svg.appendChild(dot);
  });

  const predPoints = points.filter((item) => Number.isFinite(item.pred));
  if (predPoints.length >= 2) {
    const predPolyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    predPolyline.setAttribute(
      "points",
      predPoints.map((item) => `${scaleX(item.x)},${scaleY(item.pred)}`).join(" ")
    );
    predPolyline.setAttribute("fill", "none");
    predPolyline.setAttribute("stroke", "#D7301F");
    predPolyline.setAttribute("stroke-width", "2.6");
    svg.appendChild(predPolyline);
  }

  const xTicks = [minX, (minX + maxX) / 2, maxX];
  const yTicks = [minY, (minY + maxY) / 2, maxY];

  xTicks.forEach((value) => {
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", String(scaleX(value)));
    label.setAttribute("y", String(height - padding + 28));
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("fill", "#5f5a53");
    label.setAttribute("font-size", "16");
    label.textContent = value.toFixed(2);
    svg.appendChild(label);
  });

  yTicks.forEach((value) => {
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", String(padding - 14));
    label.setAttribute("y", String(scaleY(value) + 5));
    label.setAttribute("text-anchor", "end");
    label.setAttribute("fill", "#5f5a53");
    label.setAttribute("font-size", "16");
    label.textContent = value.toFixed(2);
    svg.appendChild(label);
  });

  const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
  title.setAttribute("x", String(width / 2));
  title.setAttribute("y", "44");
  title.setAttribute("text-anchor", "middle");
  title.setAttribute("fill", "#171717");
  title.setAttribute("font-size", "28");
  title.setAttribute("font-weight", "700");
  title.textContent = "Loi de Zipf";
  svg.appendChild(title);

  const xLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
  xLabel.setAttribute("x", String(width / 2));
  xLabel.setAttribute("y", String(height - 24));
  xLabel.setAttribute("text-anchor", "middle");
  xLabel.setAttribute("fill", "#171717");
  xLabel.setAttribute("font-size", "21");
  xLabel.textContent = "log(rang)";
  svg.appendChild(xLabel);

  const yLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
  yLabel.setAttribute("x", "22");
  yLabel.setAttribute("y", String(height / 2));
  yLabel.setAttribute("text-anchor", "middle");
  yLabel.setAttribute("fill", "#171717");
  yLabel.setAttribute("font-size", "21");
  yLabel.setAttribute("transform", `rotate(-90 22 ${height / 2})`);
  yLabel.textContent = "log(fréquence)";
  svg.appendChild(yLabel);

  const legendX = width - 270;
  const legendY = 94;

  const pointLegend = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  pointLegend.setAttribute("cx", String(legendX));
  pointLegend.setAttribute("cy", String(legendY));
  pointLegend.setAttribute("r", "4.6");
  pointLegend.setAttribute("fill", "#2C7FB8");
  pointLegend.setAttribute("fill-opacity", "0.7");
  svg.appendChild(pointLegend);

  const pointLegendText = document.createElementNS("http://www.w3.org/2000/svg", "text");
  pointLegendText.setAttribute("x", String(legendX + 14));
  pointLegendText.setAttribute("y", String(legendY + 5));
  pointLegendText.setAttribute("fill", "#171717");
  pointLegendText.setAttribute("font-size", "16");
  pointLegendText.textContent = "Donnees";
  svg.appendChild(pointLegendText);

  const lineLegend = document.createElementNS("http://www.w3.org/2000/svg", "line");
  lineLegend.setAttribute("x1", String(legendX - 5));
  lineLegend.setAttribute("y1", String(legendY + 28));
  lineLegend.setAttribute("x2", String(legendX + 5));
  lineLegend.setAttribute("y2", String(legendY + 28));
  lineLegend.setAttribute("stroke", "#D7301F");
  lineLegend.setAttribute("stroke-width", "2.6");
  svg.appendChild(lineLegend);

  const lineLegendText = document.createElementNS("http://www.w3.org/2000/svg", "text");
  lineLegendText.setAttribute("x", String(legendX + 14));
  lineLegendText.setAttribute("y", String(legendY + 33));
  lineLegendText.setAttribute("fill", "#171717");
  lineLegendText.setAttribute("font-size", "16");
  lineLegendText.textContent = "Regression log-log";
  svg.appendChild(lineLegendText);

  zipfChart.appendChild(svg);
}

async function renderCsvFromFile(container, file, options = {}) {
  if (!file) {
    clearContainer(container);
    container.appendChild(createEmptyState(options.emptyMessage || "Aucun fichier CSV disponible."));
    return;
  }

  try {
    const text = await file.text();
    renderTable(container, parseCsv(text), options);
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire le tableau CSV."));
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

async function renderJsdCsvFromFile(container, file, options = {}) {
  if (!file) {
    setContainerEmptyState(container, options.emptyMessage || "Aucun tableau JSD disponible.");
    return;
  }

  try {
    const parsed = parseCsv(await file.text());
    const numericColumns = getJsdNumericColumnIndexes(parsed, options.mode || "generic");
    renderTable(container, parsed, {
      ...options,
      cellRenderer: createFixedNumericCellRenderer({
        digits: Number.isInteger(options.digits) ? options.digits : 4,
        numericColumns
      })
    });
  } catch (error) {
    setContainerEmptyState(container, "Impossible de lire le tableau CSV.");
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

async function renderJsdContributionsTable(container, file, options = {}) {
  if (!file) {
    setContainerEmptyState(container, options.emptyMessage || "Aucune contribution de termes n'est disponible.");
    return;
  }

  try {
    const parsed = parseCsv(await file.text());
    const termColumnIndex = headerIndex(parsed.headers, ["terme"]);
    const modeColumnIndex = headerIndex(parsed.headers, ["mode_comparaison"]);
    const departColumnIndex = headerIndex(parsed.headers, ["unite_depart"]);
    const arriveeColumnIndex = headerIndex(parsed.headers, ["unite_arrivee"]);
    const numericColumns = getJsdNumericColumnIndexes(parsed, "generic");
    const numericCellRenderer = createFixedNumericCellRenderer({ digits: 4, numericColumns });

    renderTable(container, parsed, {
      ...options,
      cellRenderer: (payload) => numericCellRenderer(payload),
      onCellClick: ({ row, columnIndex }) => {
        if (columnIndex !== termColumnIndex) return null;
        const termValue = String(row[termColumnIndex] || "").trim();
        if (!termValue) return null;
        return {
          clickable: true,
          onClick: () =>
            openJsdConcordancierDialog(
              row[modeColumnIndex] || "",
              row[departColumnIndex] || "",
              row[arriveeColumnIndex] || "",
              termValue
            )
        };
      }
    });
  } catch (error) {
    setContainerEmptyState(container, "Impossible de lire la table des contributions JSD.");
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

function sortTopicLabels(labels) {
  return [...labels].sort((left, right) => {
    const leftNum = Number.parseInt(String(left).replace(/[^\d-]/g, ""), 10);
    const rightNum = Number.parseInt(String(right).replace(/[^\d-]/g, ""), 10);
    if (Number.isFinite(leftNum) && Number.isFinite(rightNum)) return leftNum - rightNum;
    return String(left).localeCompare(String(right), undefined, { numeric: true });
  });
}

function getLdaTopicColor(index) {
  const palette = [
    "#9f2f2a",
    "#2c7a7b",
    "#b7791f",
    "#6b46c1",
    "#2f855a",
    "#c05621",
    "#285e61",
    "#97266d"
  ];
  return palette[index % palette.length];
}

async function renderLdaTopTermsByTopic(container, file, options = {}) {
  clearContainer(container);

  if (!file) {
    container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV de top termes LDA n'a été trouvé."));
    return;
  }

  try {
    const parsed = parseCsv(await file.text());
    if (!parsed.headers.length) {
      container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV de top termes LDA n'a été trouvé."));
      return;
    }

    const wideMatrix = parseLdaWideTopicMatrix(parsed);
    if (wideMatrix) {
      const title = document.createElement("h3");
      title.className = "result-table-section-title";
      title.textContent = options.heading || "Mots les plus probables par topic";
      container.appendChild(title);

      const caption = document.createElement("p");
      caption.className = "result-table-caption";
      caption.textContent = `${wideMatrix.topics.length} topic(s) détecté(s) dans ${file.name}.`;
      container.appendChild(caption);

      const stack = document.createElement("div");
      stack.className = "lda-topic-sections";

      wideMatrix.topics.forEach((topic) => {
        const rows = wideMatrix.topicMap.get(topic) || [];
        const topicMaxProb = rows.length ? rows[0].prob : 0;
        const topicSumProb = rows.reduce((sum, entry) => sum + (Number.isFinite(entry.prob) ? entry.prob : 0), 0);
        const rowsWithRelative = rows.map((entry) => ({
          ...entry,
          relativeProb: topicSumProb > 0 ? entry.prob / topicSumProb : Number.NaN
        }));
        const topicMaxRelative = rowsWithRelative.length
          ? Math.max(...rowsWithRelative.map((entry) => entry.relativeProb).filter((value) => Number.isFinite(value)))
          : 0;

        const section = document.createElement("section");
        section.className = "lda-topic-section";

        const heading = document.createElement("h4");
        heading.className = "lda-topic-section-title";
        heading.textContent = topic.replaceAll("_", " ");
        section.appendChild(heading);

        const tableHost = document.createElement("div");
        tableHost.className = "lda-topic-section-table";
        section.appendChild(tableHost);

        const parsedTable = {
          headers: ["Rang", "Mot", "Probabilité LDA réelle", "Score relatif (mots retenus)"],
          rows: rowsWithRelative.map((entry, index) => [
            String(index + 1),
            entry.term,
            formatTableNumber(entry.prob, 6),
            formatTableNumber(entry.relativeProb, 6)
          ])
        };

        renderTable(tableHost, parsedTable, {
          maxRows: parsedTable.rows.length,
          rowClassName: ({ rowIndex }) => {
            if (rowIndex === 0) return "is-lda-term-strong";
            if (rowIndex === 1) return "is-lda-term-medium";
            if (rowIndex === 2) return "is-lda-term-soft";
            return "";
          },
          cellClassName: ({ columnIndex }) => {
            if (columnIndex === 1) return "lda-term-cell";
            if (columnIndex === 2) return "lda-probability-cell";
            if (columnIndex === 3) return "lda-relative-score-cell";
            return "";
          },
          cellRenderer: ({ cell, columnIndex }) => {
            if (columnIndex !== 2 && columnIndex !== 3) return null;
            const probText = String(cell || "");
            const value = parseTableNumber(probText);
            const scaleMax = columnIndex === 2 ? topicMaxProb : topicMaxRelative;
            const relativeWidth = Number.isFinite(value) && Number.isFinite(scaleMax) && scaleMax > 0
              ? Math.max(8, Math.min(100, (value / scaleMax) * 100))
              : 8;
            const meterClass = columnIndex === 2 ? "lda-probability-meter" : "lda-relative-meter";
            const barClass = columnIndex === 2 ? "lda-probability-bar" : "lda-relative-bar";
            return {
              html: `<div class="${meterClass}"><span class="${barClass}" style="width:${relativeWidth}%"></span><strong class="lda-probability-value">${escapeHtml(probText)}</strong></div>`
            };
          }
        });

        stack.appendChild(section);
      });

      container.appendChild(stack);
      return;
    }

    const topicIndex = headerIndex(parsed.headers, ["topic"]);
    const termIndex = headerIndex(parsed.headers, ["term", "terme"]);
    const probIndex = headerIndex(parsed.headers, ["prob", "probability", "poids"]);

    if (topicIndex === -1 || termIndex === -1 || probIndex === -1) {
      renderTable(container, parsed, {
        title: options.title || "Top termes par topic",
        emptyMessage: options.emptyMessage
      });
      return;
    }

    const groups = new Map();
    parsed.rows.forEach((row) => {
      const topic = String(row[topicIndex] || "").trim();
      const term = String(row[termIndex] || "").trim();
      const prob = parseTableNumber(row[probIndex]);
      if (!topic || !term || !Number.isFinite(prob)) return;
      if (!groups.has(topic)) groups.set(topic, []);
      groups.get(topic).push({ term, prob });
    });

    if (!groups.size) {
      container.appendChild(createEmptyState(options.emptyMessage || "Aucun top terme LDA exploitable n'a été trouvé."));
      return;
    }

    const title = document.createElement("h3");
    title.className = "result-table-section-title";
    title.textContent = options.heading || "Mots les plus probables par topic";
    container.appendChild(title);

    const caption = document.createElement("p");
    caption.className = "result-table-caption";
    caption.textContent = `${groups.size} topic(s) détecté(s) dans ${file.name}.`;
    container.appendChild(caption);

    const stack = document.createElement("div");
    stack.className = "lda-topic-sections";

    sortTopicLabels([...groups.keys()]).forEach((topic) => {
      const rows = [...groups.get(topic)].sort((left, right) => right.prob - left.prob);
      const topicMaxProb = rows.length ? rows[0].prob : 0;
      const topicSumProb = rows.reduce((sum, entry) => sum + (Number.isFinite(entry.prob) ? entry.prob : 0), 0);
      const rowsWithRelative = rows.map((entry) => ({
        ...entry,
        relativeProb: topicSumProb > 0 ? entry.prob / topicSumProb : Number.NaN
      }));
      const topicMaxRelative = rowsWithRelative.length
        ? Math.max(...rowsWithRelative.map((entry) => entry.relativeProb).filter((value) => Number.isFinite(value)))
        : 0;

      const section = document.createElement("section");
      section.className = "lda-topic-section";

      const heading = document.createElement("h4");
      heading.className = "lda-topic-section-title";
      heading.textContent = topic.replaceAll("_", " ");
      section.appendChild(heading);

      const tableHost = document.createElement("div");
      tableHost.className = "lda-topic-section-table";
      section.appendChild(tableHost);

      const parsedTable = {
        headers: ["Rang", "Mot", "Probabilité LDA réelle", "Score relatif (mots retenus)"],
        rows: rowsWithRelative.map((entry, index) => [
          String(index + 1),
          entry.term,
          formatTableNumber(entry.prob, 6),
          formatTableNumber(entry.relativeProb, 6)
        ])
      };

      renderTable(tableHost, parsedTable, {
        maxRows: 200,
        rowClassName: ({ rowIndex }) => {
          if (rowIndex === 0) return "is-lda-term-strong";
          if (rowIndex === 1) return "is-lda-term-medium";
          if (rowIndex === 2) return "is-lda-term-soft";
          return "";
        },
        cellClassName: ({ columnIndex }) => {
          if (columnIndex === 1) return "lda-term-cell";
          if (columnIndex === 2) return "lda-probability-cell";
          if (columnIndex === 3) return "lda-relative-score-cell";
          return "";
        },
        cellRenderer: ({ cell, columnIndex }) => {
          if (columnIndex !== 2 && columnIndex !== 3) return null;
          const probText = String(cell || "");
          const value = parseTableNumber(probText);
          const scaleMax = columnIndex === 2 ? topicMaxProb : topicMaxRelative;
          const relativeWidth = Number.isFinite(value) && Number.isFinite(scaleMax) && scaleMax > 0
            ? Math.max(8, Math.min(100, (value / scaleMax) * 100))
            : 8;
          const meterClass = columnIndex === 2 ? "lda-probability-meter" : "lda-relative-meter";
          const barClass = columnIndex === 2 ? "lda-probability-bar" : "lda-relative-bar";
          return {
            html: `<div class="${meterClass}"><span class="${barClass}" style="width:${relativeWidth}%"></span><strong class="lda-probability-value">${escapeHtml(probText)}</strong></div>`
          };
        }
      });

      stack.appendChild(section);
    });

    container.appendChild(stack);
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire les top termes LDA."));
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

async function renderLdaTopicSegments(container, file, options = {}) {
  clearContainer(container);

  if (!file) {
    container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV de segments LDA n'a été trouvé."));
    return;
  }

  try {
    const fileText = await file.text();
    const groups = new Map();
    const skippedSegments = [];
    const normalizedFileName = String(file.name || file.path || "").toLowerCase();
    let topicTermLookup = new Map();

    if (options.topTermsFile) {
      try {
        const topTermsParsed = parseCsv(await options.topTermsFile.text());
        topicTermLookup = buildLdaTopicTermLookup(topTermsParsed, Number.isFinite(options.highlightTermsPerTopic) ? options.highlightTermsPerTopic : 20);
      } catch (error) {
        log(`[warn] Lecture des mots saillants LDA impossible (${options.topTermsFile.name}): ${error.message}`);
      }
    }

    const pushEntry = ({ docId, texte, topicLabel, dominantProb, segmentExploitable = true, retainedTermsCount = 0, distribution = [] }) => {
      const cleanedText = String(texte || "").replace(/\s+/g, " ").trim();
      const cleanedDocId = String(docId || "").trim();
      const cleanedTopic = String(topicLabel || "").trim();
      if (!cleanedText || !cleanedDocId) return;
      const numericDistribution = Array.isArray(distribution)
        ? distribution.map((value) => Number(value)).filter((value) => Number.isFinite(value))
        : [];
      const inferredUniform = numericDistribution.length > 1 && (Math.max(...numericDistribution) - Math.min(...numericDistribution) < 1e-9);
      if (!segmentExploitable || inferredUniform || !cleanedTopic) {
        skippedSegments.push({
          docId: cleanedDocId,
          texte: cleanedText,
          retainedTermsCount: Number.isFinite(retainedTermsCount) ? retainedTermsCount : 0
        });
        return;
      }
      if (!groups.has(cleanedTopic)) groups.set(cleanedTopic, []);
      groups.get(cleanedTopic).push({
        docId: cleanedDocId,
        texte: cleanedText,
        dominantProb
      });
    };

    if (normalizedFileName.endsWith(".json")) {
      const payload = JSON.parse(fileText);
      const units = Array.isArray(payload?.unites) ? payload.unites : [];
      units.forEach((unit) => {
        const scores = Array.isArray(unit?.distribution_topics) ? unit.distribution_topics.map((value) => Number(value)) : [];
        let dominantTopic = Number.parseInt(String(unit?.topic_dominant ?? "").replace(/[^\d-]/g, ""), 10);
        let dominantProb = Number.NaN;
        const retainedTermsCount = Number.parseInt(String(unit?.nb_termes_retenus ?? "0"), 10);
        const segmentExploitable = Boolean(unit?.segment_exploitable ?? true);
        if (!Number.isFinite(dominantTopic) && scores.length) {
          let bestIndex = -1;
          let bestScore = -Infinity;
          scores.forEach((score, index) => {
            if (Number.isFinite(score) && score > bestScore) {
              bestScore = score;
              bestIndex = index;
            }
          });
          dominantTopic = bestIndex >= 0 ? bestIndex + 1 : Number.NaN;
          dominantProb = Number.isFinite(bestScore) ? bestScore : Number.NaN;
        } else if (Number.isFinite(dominantTopic) && scores.length >= dominantTopic) {
          dominantProb = Number(scores[dominantTopic - 1]);
        }

        pushEntry({
          docId: unit?.identifiant,
          texte: unit?.texte,
          topicLabel: Number.isFinite(dominantTopic) ? `Topic_${dominantTopic}` : "Topic_inconnu",
          dominantProb,
          segmentExploitable,
          retainedTermsCount,
          distribution: scores
        });
      });
    } else {
      const parsed = parseCsv(fileText);
      if (!parsed.headers.length) {
        container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV de segments LDA n'a été trouvé."));
        return;
      }

      const textIndex = headerIndex(parsed.headers, ["texte", "text", "segment", "segment_texte"]);
      const docIdIndex = headerIndex(parsed.headers, ["doc_id", "document", "doc"]);
      const dominantTopicIndex = headerIndex(parsed.headers, ["topic_dominant", "topic dominant"]);
      const dominantProbIndex = headerIndex(parsed.headers, ["prob_topic_dominant", "prob topic dominant", "prob_dominante"]);
      const retainedTermsIndex = headerIndex(parsed.headers, ["nb_termes_retenus", "nb termes retenus"]);
      const exploitableIndex = headerIndex(parsed.headers, ["segment_exploitable", "segment exploitable"]);
      const topicColumns = parsed.headers
        .map((header, index) => ({ header: String(header || "").trim(), index }))
        .filter(({ header }) => /^topic[_\s-]*\d+/i.test(header));

      if (textIndex === -1 || docIdIndex === -1) {
        container.appendChild(
          createEmptyState("Les segments de texte LDA ne sont pas disponibles dans ce run. Relancez LDA avec la version actuelle.")
        );
        return;
      }

      parsed.rows.forEach((row) => {
        const texte = row[textIndex];
        const docId = row[docIdIndex];
        const retainedTermsCount = retainedTermsIndex !== -1 ? Number.parseInt(String(row[retainedTermsIndex] || "0"), 10) : 0;
        const exploitableRaw = exploitableIndex !== -1 ? String(row[exploitableIndex] || "").trim().toLowerCase() : "";
        const segmentExploitable = exploitableIndex !== -1
          ? ["1", "true", "vrai", "yes", "oui"].includes(exploitableRaw)
          : true;

        let topicLabel = "";
        if (dominantTopicIndex !== -1) {
          const rawTopic = String(row[dominantTopicIndex] || "").trim();
          const rawNumeric = Number.parseInt(rawTopic.replace(/[^\d-]/g, ""), 10);
          if (Number.isFinite(rawNumeric)) {
            topicLabel = `Topic_${rawNumeric}`;
          } else if (rawTopic) {
            topicLabel = canonicalizeTopicLabel(rawTopic).replace(/^topic_/, "Topic_");
          }
        }

        let dominantProb = dominantProbIndex !== -1 ? parseTableNumber(row[dominantProbIndex]) : Number.NaN;
        if (!topicLabel && topicColumns.length) {
          let bestTopic = "";
          let bestProb = -Infinity;
          topicColumns.forEach(({ header, index }) => {
            const prob = parseTableNumber(row[index]);
            if (!Number.isFinite(prob)) return;
            if (prob > bestProb) {
              bestProb = prob;
              bestTopic = header;
            }
          });
          topicLabel = bestTopic || "";
          dominantProb = Number.isFinite(bestProb) ? bestProb : dominantProb;
        }

        pushEntry({
          docId,
          texte,
          topicLabel: topicLabel || "Topic_inconnu",
          dominantProb,
          segmentExploitable,
          retainedTermsCount,
          distribution: topicColumns.map(({ index }) => parseTableNumber(row[index]))
        });
      });
    }

    const topics = sortTopicLabels([...groups.keys()]);
    if (!topics.length) {
      container.appendChild(createEmptyState("Aucun segment LDA exploitable n'a été trouvé."));
      return;
    }

    const heading = document.createElement("h3");
    heading.className = "result-table-section-title";
    heading.textContent = options.heading || "Segments de texte par topic";
    container.appendChild(heading);

    const caption = document.createElement("p");
    caption.className = "result-table-caption";
    caption.textContent = `${topics.length} topic(s) détecté(s) dans ${file.name}.`;
    container.appendChild(caption);

    const explanation = document.createElement("p");
    explanation.className = "field-help";
    explanation.textContent = "La probabilité dominante correspond à la probabilité que le segment appartienne à ce topic, et non au score d'un mot isolé.";
    container.appendChild(explanation);

    if (skippedSegments.length) {
      const warning = document.createElement("p");
      warning.className = "field-help field-help--alert";
      warning.textContent = `${skippedSegments.length} segment(s) ne contiennent aucun terme ou n-gramme retenu par le modèle et ne sont donc pas affichés dans les topics.`;
      container.appendChild(warning);
    }

    const tabs = document.createElement("div");
    tabs.className = "local-tabs";
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", "Topics LDA");
    container.appendChild(tabs);

    const panels = document.createElement("div");
    panels.className = "lda-segment-panels";
    container.appendChild(panels);

    const activateTopic = (activeTopic) => {
      tabs.querySelectorAll(".local-tab-button").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.ldaTopicTab === activeTopic);
      });
      panels.querySelectorAll(".lda-segment-panel").forEach((panel) => {
        panel.hidden = panel.dataset.ldaTopicPanel !== activeTopic;
      });
    };

    topics.forEach((topic, topicIndex) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `local-tab-button${topicIndex === 0 ? " is-active" : ""}`;
      button.dataset.ldaTopicTab = topic;
      button.textContent = topic.replaceAll("_", " ");
      button.addEventListener("click", () => activateTopic(topic));
      tabs.appendChild(button);

      const panel = document.createElement("section");
      panel.className = "lda-segment-panel";
      panel.dataset.ldaTopicPanel = topic;
      panel.hidden = topicIndex !== 0;

      const entries = [...(groups.get(topic) || [])].sort((left, right) => {
        const leftProb = Number.isFinite(left.dominantProb) ? left.dominantProb : -Infinity;
        const rightProb = Number.isFinite(right.dominantProb) ? right.dominantProb : -Infinity;
        if (rightProb !== leftProb) return rightProb - leftProb;
        return left.docId.localeCompare(right.docId, undefined, { numeric: true });
      });

      const info = document.createElement("p");
      info.className = "result-table-caption lda-segment-caption";
      info.textContent = `${entries.length} segment(s) dominés par ${topic.replaceAll("_", " ")}.`;
      panel.appendChild(info);

      const tableHost = document.createElement("div");
      panel.appendChild(tableHost);

      const highlightTerms = topicTermLookup.get(canonicalizeTopicLabel(topic)) || [];
      renderTable(tableHost, {
        headers: ["Segment de texte", "Probabilité du topic dans le segment", "doc_id"],
        rows: entries.map((entry) => [
          entry.texte,
          Number.isFinite(entry.dominantProb) ? formatTableNumber(entry.dominantProb, 6) : "",
          entry.docId
        ])
      }, {
        title: "Segments affichés",
        maxRows: Number.isFinite(options.maxRows) ? options.maxRows : 120,
        cellClassName: ({ columnIndex }) => {
          if (columnIndex === 0) return "lda-segment-text-cell";
          if (columnIndex === 1) return "lda-segment-prob-cell";
          if (columnIndex === 2) return "lda-segment-id-cell";
          return "";
        },
        cellRenderer: ({ cell, columnIndex }) => {
          if (columnIndex === 0) {
            return {
              html: `<div class="lda-segment-text">${highlightLdaSegmentTerms(String(cell || ""), highlightTerms)}</div>`
            };
          }
          return null;
        }
      });

      panels.appendChild(panel);
    });
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire les segments LDA."));
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

async function renderLdaTopTermsMatrix(container, file, options = {}) {
  clearContainer(container);

  if (!file) {
    container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV de top termes LDA n'a été trouvé."));
    return;
  }

  try {
    const parsed = parseCsv(await file.text());
    const isFallbackTopTermsFile = /(^|\/)top_terms\.csv$/i.test(String(file?.name || "")) || /(^|\/)top_terms\.csv$/i.test(String(file?.path || ""));
    if (!parsed.headers.length) {
      container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV de top termes LDA n'a été trouvé."));
      return;
    }

    const wideMatrix = parseLdaWideTopicMatrix(parsed);
    if (wideMatrix) {
      const matrixParsed = {
        headers: ["Terme", ...wideMatrix.topics.map((topic) => topic.replaceAll("_", " "))],
        rows: parsed.rows
          .map((row) => {
            const term = String(row[wideMatrix.termIndex] || "").trim();
            if (!term) return null;
            return [
              term,
              ...wideMatrix.topicColumns.map(({ index }) => {
                  const prob = parseTableNumber(row[index]);
                  return Number.isFinite(prob) ? formatTableNumber(prob, 6) : "";
                })
            ];
          })
          .filter(Boolean)
      };

      const title = document.createElement("h3");
      title.className = "result-table-section-title";
      title.textContent = "Tableau général des probabilités par mot";
      container.appendChild(title);

      if (isFallbackTopTermsFile) {
        const warning = document.createElement("p");
        warning.className = "field-help field-help--alert";
        warning.textContent = "Affichage partiel : ce tableau provient de top_terms.csv. Certaines probabilités peuvent manquer tant que topic_term_matrix.csv n'est pas exporté.";
        container.appendChild(warning);
      }

      renderTable(container, matrixParsed, {
        title: options.title || "Probabilités mot × topic",
        maxRows: matrixParsed.rows.length,
        cellClassName: ({ row, columnIndex }) => {
          if (columnIndex === 0) return "lda-matrix-term-cell";
          const numericValues = row
            .slice(1)
            .map((value) => parseTableNumber(String(value || "")))
            .filter((value) => Number.isFinite(value));
          if (!numericValues.length) return "";
          const current = parseTableNumber(String(row[columnIndex] || ""));
          const maxValue = Math.max(...numericValues);
          if (Number.isFinite(current) && Math.abs(current - maxValue) < 1e-12) {
            return "lda-matrix-max-cell";
          }
          return "";
        }
      });
      return;
    }

    const topicIndex = headerIndex(parsed.headers, ["topic"]);
    const termIndex = headerIndex(parsed.headers, ["term", "terme"]);
    const probIndex = headerIndex(parsed.headers, ["prob", "probability", "poids"]);

    if (topicIndex === -1 || termIndex === -1 || probIndex === -1) {
      renderTable(container, parsed, {
        title: options.title || "Top termes par topic",
        emptyMessage: options.emptyMessage
      });
      return;
    }

    const topicMap = new Map();
    parsed.rows.forEach((row) => {
      const topic = String(row[topicIndex] || "").trim();
      const term = String(row[termIndex] || "").trim();
      const prob = parseTableNumber(row[probIndex]);
      if (!topic || !term || !Number.isFinite(prob)) return;
      if (!topicMap.has(term)) topicMap.set(term, new Map());
      topicMap.get(term).set(topic, prob);
    });

    const topics = sortTopicLabels(
      [...new Set(parsed.rows.map((row) => String(row[topicIndex] || "").trim()).filter(Boolean))]
    );

    const entries = [...topicMap.entries()].map(([term, probs]) => {
      const values = topics.map((topic) => probs.get(topic));
      const maxProb = Math.max(...values.filter((value) => Number.isFinite(value)));
      return { term, probs, maxProb };
    });

    entries.sort((left, right) => {
      if (right.maxProb !== left.maxProb) return right.maxProb - left.maxProb;
      return left.term.localeCompare(right.term, undefined, { sensitivity: "base" });
    });

    const matrixParsed = {
      headers: ["Terme", ...topics.map((topic) => topic.replaceAll("_", " "))],
      rows: entries.map(({ term, probs }) => [
        term,
        ...topics.map((topic) => {
          const prob = probs.get(topic);
          return Number.isFinite(prob) ? formatTableNumber(prob, 6) : "";
        })
      ])
    };

    const title = document.createElement("h3");
    title.className = "result-table-section-title";
    title.textContent = "Tableau général des probabilités par mot";
    container.appendChild(title);

    if (isFallbackTopTermsFile) {
      const warning = document.createElement("p");
      warning.className = "field-help field-help--alert";
      warning.textContent = "Affichage partiel : ce tableau provient de top_terms.csv. Certaines probabilités peuvent manquer tant que topic_term_matrix.csv n'est pas exporté.";
      container.appendChild(warning);
    }

    renderTable(container, matrixParsed, {
      title: options.title || "Probabilités mot × topic",
      maxRows: matrixParsed.rows.length,
      cellClassName: ({ row, columnIndex }) => {
        if (columnIndex === 0) return "lda-matrix-term-cell";
        const numericValues = row
          .slice(1)
          .map((value) => parseTableNumber(String(value || "")))
          .filter((value) => Number.isFinite(value));
        if (!numericValues.length) return "";
        const current = parseTableNumber(String(row[columnIndex] || ""));
        const maxValue = Math.max(...numericValues);
        if (Number.isFinite(current) && Math.abs(current - maxValue) < 1e-9) {
          return "lda-matrix-max-cell";
        }
        return "";
      }
    });
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire le tableau général LDA."));
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

function parseLdaTopTermsLookup(parsed) {
  const topicIndex = headerIndex(parsed.headers, ["topic"]);
  const termIndex = headerIndex(parsed.headers, ["term", "terme"]);
  const probIndex = headerIndex(parsed.headers, ["prob", "probability", "poids"]);
  if (topicIndex === -1 || termIndex === -1 || probIndex === -1) {
    return null;
  }

  const topics = new Map();
  parsed.rows.forEach((row) => {
    const topic = String(row[topicIndex] || "").trim();
    const term = String(row[termIndex] || "").trim();
    const prob = parseTableNumber(row[probIndex]);
    if (!topic || !term || !Number.isFinite(prob)) return;
    const canonicalTopic = canonicalizeTopicLabel(topic);
    if (!topics.has(canonicalTopic)) topics.set(canonicalTopic, []);
    topics.get(canonicalTopic).push({ term, prob });
  });

  topics.forEach((entries) => entries.sort((left, right) => right.prob - left.prob));
  return topics;
}

function parseLdaWideTopicMatrix(parsed) {
  const termIndex = headerIndex(parsed.headers, ["term", "terme"]);
  if (termIndex === -1) return null;

  const topicColumns = parsed.headers
    .map((header, index) => ({ header: String(header || "").trim(), index }))
    .filter(({ header, index }) => index !== termIndex && /^topic[_\s-]*\d+/i.test(header));

  if (!topicColumns.length) return null;

  const topics = sortTopicLabels(topicColumns.map(({ header }) => header));
  const orderedTopicColumns = topics.map((topic) => topicColumns.find((column) => column.header === topic)).filter(Boolean);
  const topicMap = new Map(
    topics.map((topic) => [topic, []])
  );

  parsed.rows.forEach((row) => {
    const term = String(row[termIndex] || "").trim();
    if (!term) return;
    topicColumns.forEach(({ header, index }) => {
      const prob = parseTableNumber(row[index]);
      if (!Number.isFinite(prob)) return;
      topicMap.get(header).push({ term, prob });
    });
  });

  topicMap.forEach((entries) => entries.sort((left, right) => right.prob - left.prob));

  return {
    termIndex,
    topics,
    topicColumns: orderedTopicColumns,
    topicMap
  };
}

function parseLdaTopicGroups(parsed) {
  const wideMatrix = parseLdaWideTopicMatrix(parsed);
  if (wideMatrix) {
    return {
      topics: wideMatrix.topics,
      topicMap: wideMatrix.topicMap,
      sourceType: "matrix"
    };
  }

  const topicIndex = headerIndex(parsed.headers, ["topic"]);
  const termIndex = headerIndex(parsed.headers, ["term", "terme"]);
  const probIndex = headerIndex(parsed.headers, ["prob", "probability", "poids"]);
  if (topicIndex === -1 || termIndex === -1 || probIndex === -1) {
    return null;
  }

  const topicMap = new Map();
  parsed.rows.forEach((row) => {
    const topic = String(row[topicIndex] || "").trim();
    const term = String(row[termIndex] || "").trim();
    const prob = parseTableNumber(row[probIndex]);
    if (!topic || !term || !Number.isFinite(prob)) return;
    if (!topicMap.has(topic)) topicMap.set(topic, []);
    topicMap.get(topic).push({ term, prob });
  });

  const topics = sortTopicLabels([...topicMap.keys()]);
  topicMap.forEach((entries) => entries.sort((left, right) => right.prob - left.prob));

  return {
    topics,
    topicMap,
    sourceType: "top_terms"
  };
}

function distributePositions(count, min, max) {
  if (!count) return [];
  if (count === 1) return [(min + max) / 2];
  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_value, index) => min + (step * index));
}

function truncateLdaNodeLabel(value, maxLength = 28) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 1))}…`;
}

function buildLdaBipartiteGraph(topicGroups, options = {}) {
  const topN = Math.max(4, Number.parseInt(String(options.topN || 12), 10) || 12);
  const scoreMode = options.scoreMode === "relative" ? "relative" : "real";

  const topics = topicGroups.topics
    .map((topic, topicIndex) => {
      const entries = (topicGroups.topicMap.get(topic) || [])
        .filter((entry) => entry && entry.term && Number.isFinite(entry.prob) && entry.prob > 0)
        .slice(0, topN);
      if (!entries.length) return null;
      const retainedSum = entries.reduce((sum, entry) => sum + entry.prob, 0);
      const enrichedEntries = entries.map((entry, rank) => ({
        ...entry,
        rank,
        relativeProb: retainedSum > 0 ? entry.prob / retainedSum : 0
      }));
      return {
        key: topic,
        label: topic.replaceAll("_", " "),
        topicIndex,
        color: getLdaTopicColor(topicIndex),
        entries: enrichedEntries
      };
    })
    .filter(Boolean);

  const wordMap = new Map();
  const edges = [];

  topics.forEach((topic) => {
    topic.entries.forEach((entry) => {
      const score = scoreMode === "relative" ? entry.relativeProb : entry.prob;
      if (!Number.isFinite(score) || score <= 0) return;

      edges.push({
        topicKey: topic.key,
        topicLabel: topic.label,
        topicIndex: topic.topicIndex,
        topicColor: topic.color,
        term: entry.term,
        realProb: entry.prob,
        relativeProb: entry.relativeProb,
        score,
        rank: entry.rank
      });

      const existing = wordMap.get(entry.term) || {
        term: entry.term,
        strongestScore: -Infinity,
        strongestTopicIndex: topic.topicIndex,
        strongestTopicLabel: topic.label,
        strongestTopicColor: topic.color,
        maxRealProb: entry.prob,
        maxRelativeProb: entry.relativeProb,
        links: 0
      };

      existing.links += 1;
      existing.maxRealProb = Math.max(existing.maxRealProb, entry.prob);
      existing.maxRelativeProb = Math.max(existing.maxRelativeProb, entry.relativeProb);

      if (score > existing.strongestScore) {
        existing.strongestScore = score;
        existing.strongestTopicIndex = topic.topicIndex;
        existing.strongestTopicLabel = topic.label;
        existing.strongestTopicColor = topic.color;
      }

      wordMap.set(entry.term, existing);
    });
  });

  const words = [...wordMap.values()].sort((left, right) => {
    if (left.strongestTopicIndex !== right.strongestTopicIndex) {
      return left.strongestTopicIndex - right.strongestTopicIndex;
    }
    if (right.strongestScore !== left.strongestScore) {
      return right.strongestScore - left.strongestScore;
    }
    return left.term.localeCompare(right.term, undefined, { sensitivity: "base" });
  });

  const maxScore = edges.length
    ? Math.max(...edges.map((edge) => edge.score).filter((value) => Number.isFinite(value)))
    : 0;

  return {
    topics,
    words,
    edges,
    maxScore,
    topN,
    scoreMode,
    isPartial: topicGroups.sourceType !== "matrix"
  };
}

function buildLdaBipartiteGraphSvg(graph) {
  if (!graph.edges.length || !graph.topics.length || !graph.words.length) {
    return "";
  }

  const width = 1080;
  const wordBandHeight = Math.max(24, graph.words.length > 40 ? 22 : 26);
  const topicBandHeight = Math.max(70, graph.topics.length > 8 ? 62 : 76);
  const innerHeight = Math.max(
    320,
    Math.max(
      (graph.words.length - 1) * wordBandHeight,
      (graph.topics.length - 1) * topicBandHeight
    )
  );
  const height = innerHeight + 120;
  const topPadding = 58;
  const bottomPadding = 58;
  const topicX = 180;
  const wordX = width - 250;
  const topicNodeRadius = 12;
  const wordNodeRadius = 7;
  const controlSpan = 170;
  const topicYs = distributePositions(graph.topics.length, topPadding, height - bottomPadding);
  const wordYs = distributePositions(graph.words.length, topPadding, height - bottomPadding);
  const topicYMap = new Map(graph.topics.map((topic, index) => [topic.key, topicYs[index]]));
  const wordYMap = new Map(graph.words.map((word, index) => [word.term, wordYs[index]]));

  const gridLines = distributePositions(5, topPadding, height - bottomPadding)
    .map((y) => `<line x1="${topicX + 24}" y1="${y}" x2="${wordX - 24}" y2="${y}" class="lda-network-grid" />`)
    .join("");

  const edgesMarkup = graph.edges
    .map((edge) => {
      const startY = topicYMap.get(edge.topicKey);
      const endY = wordYMap.get(edge.term);
      const weightRatio = graph.maxScore > 0 ? edge.score / graph.maxScore : 0;
      const strokeWidth = 1.2 + (weightRatio * 6.2);
      const strokeOpacity = 0.16 + (weightRatio * 0.76);
      const controlOffset = Math.max(82, controlSpan - (edge.rank * 4));
      const path = [
        `M ${topicX + topicNodeRadius} ${startY}`,
        `C ${topicX + controlOffset} ${startY}, ${wordX - controlOffset} ${endY}, ${wordX - wordNodeRadius} ${endY}`
      ].join(" ");
      const title = [
        `${edge.topicLabel} → ${edge.term}`,
        `Score du modèle : ${formatTableNumber(edge.realProb, 6)}`
      ].join(" | ");
      return `<path d="${path}" fill="none" stroke="${edge.topicColor}" stroke-width="${strokeWidth.toFixed(2)}" stroke-opacity="${strokeOpacity.toFixed(3)}"><title>${escapeHtml(title)}</title></path>`;
    })
    .join("");

  const topicNodesMarkup = graph.topics
    .map((topic) => {
      const y = topicYMap.get(topic.key);
      return `
        <g class="lda-network-topic-node">
          <text x="${topicX - 26}" y="${y + 5}" text-anchor="end" class="lda-network-topic-label">${escapeHtml(topic.label)}</text>
          <circle cx="${topicX}" cy="${y}" r="${topicNodeRadius}" fill="${topic.color}" stroke="rgba(17,17,17,0.22)" stroke-width="1.2"></circle>
        </g>
      `;
    })
    .join("");

  const wordNodesMarkup = graph.words
    .map((word) => {
      const y = wordYMap.get(word.term);
      const label = truncateLdaNodeLabel(word.term, 34);
      const title = [
        word.term,
        `Topic dominant : ${word.strongestTopicLabel}`,
        `Score du modèle max : ${formatTableNumber(word.maxRealProb, 6)}`
      ].join(" | ");
      return `
        <g class="lda-network-word-node">
          <circle cx="${wordX}" cy="${y}" r="${wordNodeRadius}" fill="#fffdf8" stroke="${word.strongestTopicColor}" stroke-width="${word.links > 1 ? 2.2 : 1.4}"></circle>
          <text x="${wordX + 18}" y="${y + 4}" class="lda-network-word-label">${escapeHtml(label)}</text>
          <title>${escapeHtml(title)}</title>
        </g>
      `;
    })
    .join("");

  return `
    <svg class="lda-network-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Réseau topics × mots">
      <rect x="0" y="0" width="${width}" height="${height}" rx="18" ry="18" class="lda-network-background"></rect>
      ${gridLines}
      ${edgesMarkup}
      ${topicNodesMarkup}
      ${wordNodesMarkup}
    </svg>
  `;
}

async function renderLdaBipartiteNetwork(container, file, options = {}) {
  clearContainer(container);

  if (!file) {
    container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV LDA exploitable n'a été trouvé."));
    return;
  }

  try {
    const parsed = parseCsv(await file.text());
    const topicGroups = parseLdaTopicGroups(parsed);
    if (!topicGroups?.topics?.length) {
      container.appendChild(createEmptyState(options.emptyMessage || "Aucun export CSV LDA exploitable n'a été trouvé."));
      return;
    }

    const title = document.createElement("h3");
    title.className = "result-table-section-title";
    title.textContent = options.heading || "Réseau topics × mots";
    container.appendChild(title);

    const intro = document.createElement("p");
    intro.className = "result-table-caption";
    intro.textContent = "Chaque lien relie un topic à un mot. Plus le lien est visible, plus le mot est important dans ce topic.";
    container.appendChild(intro);

    const scoreHelp = document.createElement("p");
    scoreHelp.className = "field-help";
    scoreHelp.textContent = "Score du modèle : probabilité P(mot | topic) calculée par le LDA.";
    container.appendChild(scoreHelp);

    if (topicGroups.sourceType !== "matrix") {
      const warning = document.createElement("p");
      warning.className = "field-help field-help--alert";
      warning.textContent = "Affichage partiel : le réseau est construit à partir de top_terms.csv. Pour un réseau complet, relancez LDA avec topic_term_matrix.csv.";
      container.appendChild(warning);
    }

    const controls = document.createElement("div");
    controls.className = "lda-network-controls";
    controls.innerHTML = `
      <label class="lda-network-control">
        <span>Mots retenus par topic</span>
        <select data-lda-network-topn>
          <option value="10" selected>10</option>
          <option value="20">20</option>
          <option value="30">30</option>
        </select>
      </label>
    `;
    container.appendChild(controls);

    const metrics = document.createElement("p");
    metrics.className = "lda-network-metrics";
    container.appendChild(metrics);

    const canvas = document.createElement("div");
    canvas.className = "lda-network-canvas";
    container.appendChild(canvas);

    const topNSelect = controls.querySelector("[data-lda-network-topn]");
    if (topNSelect instanceof HTMLSelectElement && Number.isFinite(options.defaultTopN)) {
      topNSelect.value = String(options.defaultTopN);
    }

    const draw = () => {
      const graph = buildLdaBipartiteGraph(topicGroups, {
        scoreMode: "real",
        topN: topNSelect instanceof HTMLSelectElement ? topNSelect.value : 10
      });

      metrics.textContent = `${graph.topics.length} topic(s) · ${graph.words.length} mot(s) visibles · ${graph.edges.length} lien(s)`;

      if (!graph.edges.length) {
        canvas.innerHTML = "";
        canvas.appendChild(createEmptyState("Aucun lien exploitable n'a été trouvé pour ce réseau LDA."));
        return;
      }

      canvas.innerHTML = buildLdaBipartiteGraphSvg(graph);
    };

    topNSelect?.addEventListener("change", draw);
    draw();
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire le réseau LDA."));
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

async function renderLdaDocTopicsWithWords(container, topTermsFile, options = {}) {
  clearContainer(container);

  if (!topTermsFile) {
    container.appendChild(
      createEmptyState(options.emptyMessage || "Aucun export CSV de top termes LDA n'a été trouvé.")
    );
    return;
  }

  try {
    const parsed = parseCsv(await topTermsFile.text());
    if (!parsed.headers.length) {
      container.appendChild(
        createEmptyState(options.emptyMessage || "Aucun export CSV de top termes LDA n'a été trouvé.")
      );
      return;
    }

    const topicIndex = headerIndex(parsed.headers, ["topic"]);
    const termIndex = headerIndex(parsed.headers, ["term", "terme"]);
    const probIndex = headerIndex(parsed.headers, ["prob", "probability", "poids"]);

    if (topicIndex === -1 || termIndex === -1 || probIndex === -1) {
      renderTable(container, parsed, {
        title: options.title || "Mots classés par topic",
        emptyMessage: options.emptyMessage
      });
      return;
    }

    const groups = new Map();
    parsed.rows.forEach((row) => {
      const topic = String(row[topicIndex] || "").trim();
      const term = String(row[termIndex] || "").trim();
      const prob = parseTableNumber(row[probIndex]);
      if (!topic || !term || !Number.isFinite(prob)) return;
      if (!groups.has(topic)) groups.set(topic, []);
      groups.get(topic).push({ term, prob });
    });

    const topics = sortTopicLabels([...groups.keys()]);
    const orderedGroups = topics.map((topic) =>
      [...groups.get(topic)].sort((left, right) => right.prob - left.prob)
    );
    const maxRank = orderedGroups.reduce((acc, rows) => Math.max(acc, rows.length), 0);

    const parsedTable = {
      headers: ["Rang", ...topics.map((topic) => topic.replaceAll("_", " "))],
      rows: Array.from({ length: maxRank }, (_, rankIndex) => [
        String(rankIndex + 1),
        ...orderedGroups.map((rows) => {
          const entry = rows[rankIndex];
          if (!entry) return "—";
          return `${entry.term}|||${formatTableNumber(entry.prob, 6)}`;
        })
      ])
    };

    const title = document.createElement("h3");
    title.className = "result-table-section-title";
    title.textContent = "Tableau des mots par topic";
    container.appendChild(title);

    renderTable(container, parsedTable, {
      title: options.title || "Tableau des mots par topic",
      maxRows: 250,
      cellRenderer: ({ cell, columnIndex }) => {
        if (columnIndex === 0) return null;
        const raw = String(cell || "");
        if (!raw.includes("|||")) return null;
        const [term, prob] = raw.split("|||");
        return {
          html: `<strong>${escapeHtml(term)}</strong><br><span class="lda-topic-inline-prob">${escapeHtml(prob)}</span>`
        };
      },
      cellClassName: ({ row, columnIndex }) => {
        if (columnIndex > 0) return "lda-matrix-term-cell";
        return "";
      }
    });
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire le tableau des mots par topic LDA."));
    log(`[error] Lecture CSV impossible (${topTermsFile.name}): ${error.message}`);
  }
}

async function renderLdaDocTopicsSummary(container, file, options = {}) {
  clearContainer(container);

  if (!file) {
    container.appendChild(
      createEmptyState(options.emptyMessage || "Aucun export CSV de distribution topics/documents n'a été trouvé.")
    );
    return;
  }

  try {
    const parsed = parseCsv(await file.text());
    if (!parsed.headers.length) {
      container.appendChild(
        createEmptyState(options.emptyMessage || "Aucun export CSV de distribution topics/documents n'a été trouvé.")
      );
      return;
    }

    const docIdIndex = headerIndex(parsed.headers, ["doc_id", "document", "doc"]);
    const topicColumns = parsed.headers
      .map((header, index) => ({ header: String(header || "").trim(), index }))
      .filter(({ header, index }) => index !== docIdIndex && /^topic[_\s-]*\d+/i.test(header));

    if (!topicColumns.length) {
      renderTable(container, parsed, {
        title: options.title || "Distribution topics / documents",
        emptyMessage: options.emptyMessage
      });
      return;
    }

    const summaryByTopic = new Map(
      topicColumns.map(({ header }) => [
        header,
        { docs: 0, sumProb: 0, maxProb: 0 }
      ])
    );

    parsed.rows.forEach((row) => {
      let bestTopic = null;
      let bestProb = -Infinity;
      topicColumns.forEach(({ header, index }) => {
        const prob = parseTableNumber(row[index]);
        if (!Number.isFinite(prob)) return;
        if (prob > bestProb) {
          bestProb = prob;
          bestTopic = header;
        }
      });

      if (!bestTopic || !Number.isFinite(bestProb)) return;
      const bucket = summaryByTopic.get(bestTopic);
      bucket.docs += 1;
      bucket.sumProb += bestProb;
      bucket.maxProb = Math.max(bucket.maxProb, bestProb);
    });

    const summaryParsed = {
      headers: ["Topic", "Segments dominés", "Part des segments", "Probabilité moyenne", "Probabilité max"],
      rows: sortTopicLabels([...summaryByTopic.keys()]).map((topic) => {
        const item = summaryByTopic.get(topic);
        const share = parsed.rows.length > 0 ? item.docs / parsed.rows.length : 0;
        const avgProb = item.docs > 0 ? item.sumProb / item.docs : 0;
        return [
          topic.replaceAll("_", " "),
          String(item.docs),
          `${formatTableNumber(share * 100, 1)} %`,
          `${formatTableNumber(avgProb * 100, 1)} %`,
          `${formatTableNumber(item.maxProb * 100, 1)} %`
        ];
      })
    };

    const title = document.createElement("h3");
    title.className = "result-table-section-title";
    title.textContent = "Répartition dominante des segments par topic";
    container.appendChild(title);

    renderTable(container, summaryParsed, {
      title: options.title || "Synthèse topics / documents",
      maxRows: topicColumns.length,
      rowClassName: ({ rowIndex }) => `lda-summary-row lda-summary-row--${rowIndex % 4}`
    });
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire la distribution topics/documents."));
    log(`[error] Lecture CSV impossible (${file.name}): ${error.message}`);
  }
}

function headerIndex(headers, candidates) {
  const normalized = headers.map((header) => String(header || "").replace(/^\ufeff/, "").trim().toLowerCase());
  for (const candidate of candidates) {
    const index = normalized.indexOf(candidate.toLowerCase());
    if (index !== -1) return index;
  }
  return -1;
}

function canonicalizeTopicLabel(value) {
  const raw = String(value || "").replace(/^\ufeff/, "").trim();
  if (!raw) return "";

  const numericMatch = raw.match(/(\d+)/);
  if (numericMatch) {
    return `topic_${Number.parseInt(numericMatch[1], 10)}`;
  }

  return raw
    .toLowerCase()
    .replace(/[\s-]+/g, "_")
    .replace(/_+/g, "_");
}

function sortClassLabels(labels) {
  return [...labels].sort((left, right) => {
    const leftNum = Number.parseInt(String(left).replace(/[^\d-]/g, ""), 10);
    const rightNum = Number.parseInt(String(right).replace(/[^\d-]/g, ""), 10);
    if (Number.isFinite(leftNum) && Number.isFinite(rightNum)) return leftNum - rightNum;
    return String(left).localeCompare(String(right), undefined, { numeric: true });
  });
}

function parseTableNumber(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return Number.NaN;
  const normalized = raw.replace(/\s+/g, "").replace(",", ".");
  return Number.parseFloat(normalized);
}

function formatTableNumber(value, digits) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return numeric.toFixed(digits);
}

function normalizeAsciiKey(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function isStrictNumericCellValue(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return false;
  return /^-?\d+(?:[.,]\d+)?(?:e[+-]?\d+)?$/i.test(raw);
}

function createFixedNumericCellRenderer({ digits = 4, numericColumns = [] } = {}) {
  const numericSet = new Set(
    Array.isArray(numericColumns)
      ? numericColumns.filter((index) => Number.isInteger(index) && index >= 0)
      : []
  );

  return ({ cell, columnIndex }) => {
    if (!numericSet.has(columnIndex)) return null;
    if (!isStrictNumericCellValue(cell)) return null;
    const numeric = parseTableNumber(cell);
    if (!Number.isFinite(numeric)) return null;
    return {
      text: Number.isInteger(numeric) ? String(numeric) : formatTableNumber(numeric, digits)
    };
  };
}

function getJsdNumericColumnIndexes(parsed, mode = "generic") {
  if (!parsed || !Array.isArray(parsed.headers)) return [];

  if (mode === "matrix") {
    return parsed.headers
      .map((_, index) => index)
      .filter((index) => index > 0);
  }

  const numericHeaderKeys = new Set([
    "tokens_total",
    "types_total",
    "entropie_lexicale",
    "entropie_normalisee",
    "redondance_relative",
    "divergence_jensen_shannon",
    "valeur_detection",
    "score_standardise",
    "frequence_relative_depart",
    "frequence_relative_arrivee",
    "difference_relative",
    "contribution_jensen_shannon"
  ]);

  return parsed.headers.reduce((acc, header, index) => {
    const normalizedHeader = normalizeAsciiKey(header).replace(/\s+/g, "_");
    if (numericHeaderKeys.has(normalizedHeader)) {
      acc.push(index);
    }
    return acc;
  }, []);
}

function formatScientificNumber(value, digits = 6) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  if (numeric === 0) return "0";
  return numeric.toExponential(Math.max(0, digits - 1));
}

function normalizeChdTypeValue(value) {
  const normalized = String(value ?? "").trim().toLowerCase();
  return ["", "na", "nan", "null", "undefined"].includes(normalized) ? "" : normalized;
}

function formatAfcFrequencyValue(value) {
  const numeric = parseTableNumber(value);
  if (!Number.isFinite(numeric)) return String(value ?? "");
  return Number.isInteger(numeric) ? String(numeric) : formatTableNumber(numeric, 6);
}

function highlightAfcSegment(segment, term) {
  const rawSegment = String(segment ?? "");
  const normalizedTerm = String(term ?? "").trim();
  if (!rawSegment.trim() || !normalizedTerm) {
    return escapeHtml(rawSegment);
  }

  const regex = buildLooseTermRegex(normalizedTerm, "giu");
  let found = false;
  const highlighted = rawSegment.replace(regex, (_match, prefix, core, suffix) => {
    found = true;
    return `${escapeHtml(prefix)}<span class="afc-highlight">${escapeHtml(core)}</span>${escapeHtml(suffix)}`;
  });

  return found ? highlighted : escapeHtml(rawSegment);
}

async function renderAfcTermsByClass(container, file, options = {}) {
  clearContainer(container);

  if (!file) {
    container.appendChild(createEmptyState(options.emptyMessage || "Le fichier afc/stats_termes.csv est absent."));
    return;
  }

  try {
    const parsed = parseCsv(await file.text());
    if (!parsed.headers.length) {
      container.appendChild(createEmptyState(options.emptyMessage || "Le fichier afc/stats_termes.csv est absent."));
      return;
    }

    const classIndex = headerIndex(parsed.headers, ["classe_max"]);
    const termIndex = headerIndex(parsed.headers, ["terme"]);
    const frequencyIndex = headerIndex(parsed.headers, ["frequency"]);
    const chi2Index = headerIndex(parsed.headers, ["chi2"]);
    const pValueIndex = headerIndex(parsed.headers, ["p_value"]);
    const segmentIndex = headerIndex(parsed.headers, ["segment_texte"]);

    if (classIndex === -1 || termIndex === -1) {
      renderTable(container, parsed, {
        title: options.title || "stats_termes.csv",
        emptyMessage: options.emptyMessage
      });
      return;
    }

    const groups = new Map();
    parsed.rows.forEach((row) => {
      const classLabel = String(row[classIndex] || "").trim();
      if (!classLabel) return;
      if (!groups.has(classLabel)) groups.set(classLabel, []);
      groups.get(classLabel).push(row);
    });

    if (!groups.size) {
      container.appendChild(createEmptyState("AFC mots : aucune classe disponible."));
      return;
    }

    for (const classLabel of sortClassLabels(groups.keys())) {
      const section = document.createElement("section");
      section.className = "result-pane--spaced";

      const heading = document.createElement("h4");
      heading.className = "result-table-section-title";
      heading.textContent = classLabel;
      section.appendChild(heading);

      const rows = [...(groups.get(classLabel) || [])];
      if (chi2Index !== -1) {
        rows.sort((left, right) => parseTableNumber(right[chi2Index]) - parseTableNumber(left[chi2Index]));
      }

      const limitedRows = rows.slice(0, 100).map((row) => [
        termIndex === -1 ? "" : String(row[termIndex] ?? ""),
        frequencyIndex === -1 ? "" : formatAfcFrequencyValue(row[frequencyIndex]),
        chi2Index === -1 ? "" : formatTableNumber(parseTableNumber(row[chi2Index]), 6),
        pValueIndex === -1 ? "" : formatTableNumber(parseTableNumber(row[pValueIndex]), 6),
        segmentIndex === -1 ? "" : String(row[segmentIndex] ?? "")
      ]);

      renderTable(
        section,
        {
          headers: ["Terme", "frequency", "chi2", "p_value", "Segment_texte"],
          rows: limitedRows
        },
        {
          title: classLabel,
          maxRows: limitedRows.length,
          cellRenderer: ({ cell, row, columnIndex, headers }) => {
            const segmentColumnIndex = headerIndex(headers, ["segment_texte"]);
            const termColumnIndex = headerIndex(headers, ["terme"]);
            if (columnIndex === segmentColumnIndex) {
              return {
                html: highlightAfcSegment(cell, row[termColumnIndex]),
                className: "afc-segment-cell"
              };
            }
            return null;
          }
        }
      );

      container.appendChild(section);
    }
  } catch (error) {
    clearContainer(container);
    container.appendChild(createEmptyState("Impossible de lire la table AFC des termes."));
    log(`[error] Lecture AFC termes impossible (${file.name}) : ${error.message}`);
  }
}

function extractChdStatsCloneParsed(parsed, classLabel, options = {}) {
  const significanceThreshold = Number.isFinite(options.significanceThreshold)
    ? options.significanceThreshold
    : 0.05;

  if (!parsed?.headers?.length) {
    return {
      headers: ["Message"],
      rows: [["Statistiques indisponibles."]],
      rowClasses: []
    };
  }

  const classIndex = headerIndex(parsed.headers, ["classe"]);
  const termIndex = headerIndex(parsed.headers, ["terme"]);
  if (classIndex === -1 || termIndex === -1) {
    return {
      headers: ["Message"],
      rows: [["Statistiques indisponibles."]],
      rowClasses: []
    };
  }

  const chi2Index = headerIndex(parsed.headers, ["chi2"]);
  const frequencyIndex = headerIndex(parsed.headers, ["frequency"]);
  const effStIndex = headerIndex(parsed.headers, ["eff_st"]);
  const effTotalIndex = headerIndex(parsed.headers, ["eff_total"]);
  const percentageIndex = headerIndex(parsed.headers, ["pourcentage"]);
  const pIndex = headerIndex(parsed.headers, ["p", "p_value"]);
  const pScientificIndex = headerIndex(parsed.headers, ["p_scientifique"]);
  const pThresholdIndex = headerIndex(parsed.headers, ["p_seuil_01"]);
  const typeIndex = headerIndex(parsed.headers, ["type", "pos"]);

  let rows = parsed.rows.filter((row) => normalizeClassValue(row[classIndex]) === normalizeClassValue(classLabel));

  if (chi2Index !== -1) {
    rows = rows.filter((row) => {
      const chi2 = parseTableNumber(row[chi2Index]);
      return Number.isFinite(chi2) && chi2 > 0;
    });

    rows.sort((left, right) => {
      const rightChi2 = parseTableNumber(right[chi2Index]);
      const leftChi2 = parseTableNumber(left[chi2Index]);
      if (rightChi2 !== leftChi2) return rightChi2 - leftChi2;

      const rightFrequency = frequencyIndex === -1 ? Number.NEGATIVE_INFINITY : parseTableNumber(right[frequencyIndex]);
      const leftFrequency = frequencyIndex === -1 ? Number.NEGATIVE_INFINITY : parseTableNumber(left[frequencyIndex]);
      return rightFrequency - leftFrequency;
    });
  }

  if (!rows.length) {
    return {
      headers: ["Message"],
      rows: [["Aucun terme disponible pour cette classe avec les filtres actuels."]],
      rowClasses: []
    };
  }

  const cloneRows = rows.map((row, index) => {
    const frequency = frequencyIndex === -1 ? Number.NaN : parseTableNumber(row[frequencyIndex]);
    const effTotalRaw = effTotalIndex === -1 ? Number.NaN : parseTableNumber(row[effTotalIndex]);
    const effTotal = Number.isFinite(effTotalRaw) ? effTotalRaw : frequency;

    const docprop = headerIndex(parsed.headers, ["docprop"]) === -1
      ? Number.NaN
      : parseTableNumber(row[headerIndex(parsed.headers, ["docprop"])]);

    const effStRaw = effStIndex === -1 ? Number.NaN : parseTableNumber(row[effStIndex]);
    const effSt = Number.isFinite(effStRaw)
      ? effStRaw
      : (Number.isFinite(docprop) && Number.isFinite(effTotal) ? Math.round(docprop * effTotal) : Number.NaN);

    const percentageRaw = percentageIndex === -1 ? Number.NaN : parseTableNumber(row[percentageIndex]);
    const percentage = Number.isFinite(percentageRaw)
      ? percentageRaw
      : (Number.isFinite(effSt) && Number.isFinite(effTotal) && effTotal > 0 ? (100 * effSt) / effTotal : Number.NaN);

    const chi2 = chi2Index === -1 ? Number.NaN : parseTableNumber(row[chi2Index]);
    const pValue = pIndex === -1 ? Number.NaN : parseTableNumber(row[pIndex]);
    const pScientificValue = pScientificIndex === -1
      ? formatScientificNumber(pValue, 6)
      : String(row[pScientificIndex] ?? "").trim();
    const pThresholdValue = pThresholdIndex === -1
      ? (Number.isFinite(pValue) && pValue <= 0.01 ? "p <= 0.01" : "")
      : String(row[pThresholdIndex] ?? "").trim();
    const typeValue = typeIndex === -1 ? "" : normalizeChdTypeValue(row[typeIndex]);

    return {
      values: [
        String(index),
        String(row[termIndex] ?? ""),
        Number.isFinite(effSt) ? String(Math.round(effSt)) : "",
        Number.isFinite(effTotal) ? String(Math.round(effTotal)) : "",
        formatTableNumber(percentage, 2),
        formatTableNumber(chi2, 3),
        formatTableNumber(pValue, 6),
        pScientificValue,
        pThresholdValue,
        typeValue
      ],
      nonSignificant: Number.isFinite(pValue) && pValue > significanceThreshold
    };
  });

  return {
    headers: ["num", "forme", "eff. s.t.", "eff. total", "pourcentage", "chi2", "p.value", "p.value (sci.)", "seuil p", "Type"],
    rows: cloneRows.map((entry) => entry.values),
    rowClasses: cloneRows.map((entry) => (entry.nonSignificant ? "is-chd-non-significant" : ""))
  };
}

function renderChdStatsByClass(container, parsed, options = {}) {
  clearContainer(container);

  if (!parsed || !parsed.headers.length) {
    container.appendChild(createEmptyState(options.emptyMessage || "Aucune statistique CHD disponible."));
    return;
  }

  const classColumnIndex = headerIndex(parsed.headers, ["classe", "classe_brut"]);
  if (classColumnIndex === -1) {
    renderTable(container, parsed, options);
    return;
  }

  const groups = new Map();
  parsed.rows.forEach((row) => {
    const rawClass = String(row[classColumnIndex] || "").trim();
    const classLabel = normalizeClassValue(rawClass);
    if (!groups.has(classLabel)) groups.set(classLabel, []);
    groups.get(classLabel).push(row);
  });

  if (!groups.size) {
    renderTable(container, parsed, options);
    return;
  }

  const tabs = document.createElement("div");
  tabs.className = "local-tabs";

  const panelsWrap = document.createElement("div");
  panelsWrap.className = "local-tab-panels";

  const descriptors = sortClassLabels(groups.keys()).map((label) => ({
    label: label === "Sans classe" ? label : `Classe ${label}`,
    rows: groups.get(label)
  }));

  descriptors.forEach((descriptor, index) => {
    const maxPValue = parseTableNumber(document.getElementById("maxP")?.value);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `local-tab-button${index === 0 ? " is-active" : ""}`;
    button.textContent = descriptor.label;

    const panel = document.createElement("section");
    panel.className = `local-tab-panel${index === 0 ? " is-active" : ""}`;
    panel.hidden = index !== 0;

    const cloneParsed = extractChdStatsCloneParsed(parsed, descriptor.label, {
      significanceThreshold: Number.isFinite(maxPValue) ? maxPValue : 0.05
    });

    renderTable(
      panel,
      { headers: cloneParsed.headers, rows: cloneParsed.rows },
      {
        title: descriptor.label,
        maxRows: cloneParsed.rows.length,
        emptyMessage: options.emptyMessage,
        rowClassName: ({ rowIndex }) => cloneParsed.rowClasses[rowIndex] || "",
        cellClassName: ({ rowIndex, columnIndex, headers }) => {
          const isNonSignificant = cloneParsed.rowClasses[rowIndex] === "is-chd-non-significant";
          if (!isNonSignificant) return "";
          const termColumnIndex = headerIndex(headers, ["forme", "terme"]);
          const pValueColumnIndexes = [
            headerIndex(headers, ["p.value", "p_value", "p"]),
            headerIndex(headers, ["p.value (sci.)"]),
            headerIndex(headers, ["seuil p"])
          ].filter((value) => value !== -1);
          if (columnIndex === termColumnIndex || pValueColumnIndexes.includes(columnIndex)) {
            return "is-chd-non-significant-cell";
          }
          return "";
        },
        onCellClick: ({ cell, rowIndex, columnIndex, headers }) => {
          const termColumnIndex = headerIndex(headers, ["forme", "terme"]);
          if (columnIndex !== termColumnIndex) return null;
          const termValue = String(cell || "").trim();
          if (!termValue) return null;
          const isNonSignificant = cloneParsed.rowClasses[rowIndex] === "is-chd-non-significant";
          return {
            clickable: true,
            className: isNonSignificant ? "is-chd-non-significant-cell" : "",
            onClick: () => openTermSegmentsDialog(normalizeClassValue(descriptor.label), termValue),
            onContextMenu: (event) =>
              openChdTermContextMenu({
                event,
                term: termValue,
                classLabel: normalizeClassValue(descriptor.label)
              })
          };
        }
      }
    );

    button.addEventListener("click", () => {
      tabs.querySelectorAll(".local-tab-button").forEach((item) => item.classList.remove("is-active"));
      panelsWrap.querySelectorAll(".local-tab-panel").forEach((item) => {
        item.classList.remove("is-active");
        item.hidden = true;
      });
      button.classList.add("is-active");
      panel.classList.add("is-active");
      panel.hidden = false;
    });

    tabs.appendChild(button);
    panelsWrap.appendChild(panel);
  });

  container.appendChild(tabs);
  container.appendChild(panelsWrap);
}

async function renderCombinedTables(container, descriptors, emptyMessage) {
  clearContainer(container);

  const available = descriptors.filter((descriptor) => descriptor.file);
  if (!available.length) {
    container.appendChild(createEmptyState(emptyMessage));
    return;
  }

  for (const descriptor of available) {
    const section = document.createElement("section");
    section.className = "result-pane--spaced";

    try {
      const text = await descriptor.file.text();
      renderTable(section, parseCsv(text), {
        title: descriptor.title,
        maxRows: descriptor.maxRows || 60,
        emptyMessage
      });
    } catch (error) {
      section.appendChild(createEmptyState(`Lecture impossible pour ${descriptor.title}.`));
      log(`[error] Lecture CSV impossible (${descriptor.file.name}): ${error.message}`);
    }

    container.appendChild(section);
  }
}

function isLongitudinalUiAvailable() {
  return [
    resultContainers.suiviMeta,
    resultContainers.suiviIndicatorsTable,
    resultContainers.suiviEntropyPlot
  ].every((container) => container instanceof HTMLElement);
}

async function renderLongitudinalExports(index) {
  if (!isLongitudinalUiAvailable()) {
    appState.jsdConcordancierRows = [];
    appState.suiviPresentation = {
      layer: "lexicale_brute",
      emotionLexicon: "",
      hasEmotionProfiles: false,
      hasValenceProfiles: false,
      note: ""
    };
    return;
  }

  appState.jsdConcordancierRows = [];
  appState.suiviPresentation = {
    layer: "lexicale_brute",
    emotionLexicon: "",
    hasEmotionProfiles: false,
    hasValenceProfiles: false,
    note: ""
  };

  const suiviMetaFile = findFile(index, [(path) => path.endsWith("sante/suivi_meta.csv")]);
  if (suiviMetaFile) {
    try {
      const parsedMeta = parseCsv(await suiviMetaFile.text());
      extractSuiviPresentationFromMeta(parsedMeta);
      renderTable(resultContainers.suiviMeta, parsedMeta, {
        title: "suivi_meta.csv",
        emptyMessage: "Aucune métadonnée de suivi n'est disponible."
      });
    } catch (error) {
      setContainerEmptyState(resultContainers.suiviMeta, "Aucune métadonnée de suivi n'est disponible.");
      log(`[error] Lecture CSV impossible (${suiviMetaFile.name}) : ${error.message}`);
      applySuiviPresentation();
    }
  } else {
    setContainerEmptyState(resultContainers.suiviMeta, "Aucune métadonnée de suivi n'est disponible.");
    applySuiviPresentation();
  }

  await renderJsdCsvFromFile(
    resultContainers.suiviIndicatorsTable,
    findFile(index, [(path) => path.endsWith("sante/indicateurs_entretiens.csv")]),
    {
      title: "indicateurs_entretiens.csv",
      emptyMessage: "Aucun indicateur par entretien n'a été calculé."
    }
  );

  renderImage(
    resultContainers.suiviEntropyPlot,
    findFile(index, [(path) => path.endsWith("sante/entropie_lexicale.png")]),
    "Entropie lexicale par entretien"
  );
  makeResultImagePreviewable(resultContainers.suiviEntropyPlot, "Entropie lexicale", "Trajectoire lexicale");

  renderImage(
    resultContainers.suiviRedundancyPlot,
    findFile(index, [(path) => path.endsWith("sante/redondance_relative.png")]),
    "Redondance relative par entretien"
  );
  makeResultImagePreviewable(resultContainers.suiviRedundancyPlot, "Redondance relative", "Trajectoire lexicale");

  const emotionProfilesPlotFile = findFile(index, [(path) => path.endsWith("sante/profils_emotionnels.png")]);
  const valenceProfilesPlotFile = findFile(index, [(path) => path.endsWith("sante/profils_valence.png")]);
  appState.suiviPresentation.hasEmotionProfiles = Boolean(emotionProfilesPlotFile);
  appState.suiviPresentation.hasValenceProfiles = Boolean(valenceProfilesPlotFile);
  applySuiviPresentation();
  const suiviNote = getMeaningfulSuiviNote(appState.suiviPresentation.note);
  const emotionEmptyMessage = appState.suiviPresentation.layer === "emotionnelle"
    ? (suiviNote || "Aucun profil émotionnel n'est disponible pour cette trajectoire.")
    : "Disponible uniquement pour la trajectoire émotionnelle.";
  const valenceEmptyMessage = appState.suiviPresentation.layer === "emotionnelle"
    ? (suiviNote || "Aucun résumé de valence n'est disponible pour cette trajectoire.")
    : "Disponible uniquement pour la trajectoire émotionnelle.";

  renderImage(
    resultContainers.suiviEmotionProfilesPlot,
    emotionProfilesPlotFile,
    "Profils émotionnels",
    emotionEmptyMessage
  );
  makeResultImagePreviewable(resultContainers.suiviEmotionProfilesPlot, "Profils émotionnels", "Trajectoire lexicale");

  await renderJsdCsvFromFile(
    resultContainers.suiviEmotionProfilesTable,
    findFile(index, [(path) => path.endsWith("sante/profils_emotionnels.csv")]),
    {
      mode: "matrix",
      title: "profils_emotionnels.csv",
      emptyMessage: emotionEmptyMessage
    }
  );

  renderImage(
    resultContainers.suiviValenceProfilesPlot,
    valenceProfilesPlotFile,
    "Résumé de valence positive / négative",
    valenceEmptyMessage
  );
  makeResultImagePreviewable(resultContainers.suiviValenceProfilesPlot, "Résumé de valence positive / négative", "Trajectoire lexicale");

  await renderJsdCsvFromFile(
    resultContainers.suiviValenceProfilesTable,
    findFile(index, [(path) => path.endsWith("sante/profils_valence.csv")]),
    {
      mode: "matrix",
      title: "profils_valence.csv",
      emptyMessage: valenceEmptyMessage
    }
  );

  renderImage(
    resultContainers.suiviJsdSuccessivePlot,
    findFile(index, [(path) => path.endsWith("sante/divergence_jensen_shannon_successive.png")]),
    "Divergence de Jensen-Shannon entre séances successives"
  );
  makeResultImagePreviewable(
    resultContainers.suiviJsdSuccessivePlot,
    "Divergence de Jensen-Shannon entre séances successives",
    "Trajectoire lexicale"
  );

  await renderJsdCsvFromFile(
    resultContainers.suiviJsdSuccessiveTable,
    findFile(index, [(path) => path.endsWith("sante/divergence_jensen_shannon_successive.csv")]),
    {
      title: "divergence_jensen_shannon_successive.csv",
      emptyMessage: "Aucune divergence de Jensen-Shannon entre séances successives n'a été calculée."
    }
  );

  renderImage(
    resultContainers.suiviJsdReferencePlot,
    findFile(index, [(path) => path.endsWith("sante/divergence_jensen_shannon_reference.png")]),
    "Divergence de Jensen-Shannon par rapport à la première séance"
  );
  makeResultImagePreviewable(
    resultContainers.suiviJsdReferencePlot,
    "Divergence de Jensen-Shannon par rapport à la première séance",
    "Trajectoire lexicale"
  );

  await renderJsdCsvFromFile(
    resultContainers.suiviJsdReferenceTable,
    findFile(index, [(path) => path.endsWith("sante/divergence_jensen_shannon_reference.csv")]),
    {
      title: "divergence_jensen_shannon_reference.csv",
      emptyMessage: "Aucune divergence de Jensen-Shannon par rapport à la première séance n'a été calculée."
    }
  );

  renderImage(
    resultContainers.suiviRupturesPlot,
    findFile(index, [(path) => path.endsWith("sante/detection_ruptures_discursives.png")]),
    "Détection explicite des ruptures discursives"
  );
  makeResultImagePreviewable(
    resultContainers.suiviRupturesPlot,
    "Détection explicite des ruptures discursives",
    "Trajectoire lexicale"
  );

  await renderJsdCsvFromFile(
    resultContainers.suiviRupturesTable,
    findFile(index, [(path) => path.endsWith("sante/detection_ruptures_discursives.csv")]),
    {
      title: "detection_ruptures_discursives.csv",
      emptyMessage: "Aucune détection explicite des ruptures n'est disponible."
    }
  );

  await renderJsdCsvFromFile(
    resultContainers.suiviTermsTable,
    findFile(index, [(path) => path.endsWith("sante/termes_evolution.csv")]),
    {
      title: "termes_evolution.csv",
      emptyMessage: "Aucun terme en évolution n'a été calculé."
    }
  );

  const jsdConcordancierFile = findFile(index, [(path) => path.endsWith("sante/concordancier_jsd.csv")]);
  if (jsdConcordancierFile) {
    try {
      appState.jsdConcordancierRows = parseJsdConcordancierRows(parseCsv(await jsdConcordancierFile.text()));
    } catch (error) {
      appState.jsdConcordancierRows = [];
      log(`[error] Lecture du concordancier JSD impossible (${jsdConcordancierFile.name}) : ${error.message}`);
    }
  }

  await renderJsdContributionsTable(
    resultContainers.suiviContributionsTable,
    findFile(index, [(path) => path.endsWith("sante/contributions_divergence_jensen_shannon.csv")]),
    {
      title: "contributions_divergence_jensen_shannon.csv",
      emptyMessage: "Aucune contribution des termes à la divergence n'a été calculée."
    }
  );

  const suiviFriseEmergencesFiles = findFiles(
    index,
    (path) => path.endsWith(".png") && path.includes("sante/frises_emergences/")
  )
    .sort((left, right) => left.path.localeCompare(right.path, undefined, { numeric: true }))
    .map(({ path, file }) => {
      const modeRaw = String(path || "")
        .replace(/^.*\//, "")
        .replace(/\.png$/i, "")
        .replace(/^frise_emergences__/, "");
      const modeTitle = (() => {
        const human = humanizeSuiviComparisonMode(modeRaw);
        if (human === "Première séance") {
          return "Première séance vs toutes les autres";
        }
        if (human === "Séance précédente") {
          return "Comparaisons entre séances successives";
        }
        return human;
      })();
      return {
        file,
        title: `Frise des émergences · ${modeTitle}`
      };
    });

  renderImageGallery(
    resultContainers.suiviFrisesEmergences,
    suiviFriseEmergencesFiles,
    "Aucune frise des émergences disponible pour la trajectoire lexicale.",
    { previewKicker: "Trajectoire lexicale" }
  );

  const suiviDivergentBarFiles = findFiles(
    index,
    (path) => path.endsWith(".png") && path.includes("sante/barres_divergentes/")
  )
    .sort((left, right) => left.path.localeCompare(right.path, undefined, { numeric: true }))
    .map(({ path, file }) => {
      return {
        file,
        title: formatSuiviGalleryTitle(path, "barres_divergentes") || "Barres divergentes"
      };
    });

  renderImageGallery(
    resultContainers.suiviDivergentBars,
    suiviDivergentBarFiles,
    "Aucune barre divergente disponible pour la trajectoire lexicale.",
    { previewKicker: "Trajectoire lexicale" }
  );

  const suiviWaterfallFiles = findFiles(
    index,
    (path) => path.endsWith(".png") && path.includes("sante/waterfalls/")
  )
    .sort((left, right) => left.path.localeCompare(right.path, undefined, { numeric: true }))
    .map(({ path, file }) => {
      return {
        file,
        title: formatSuiviGalleryTitle(path, "waterfall") || "Waterfall"
      };
    });

  renderImageGallery(
    resultContainers.suiviWaterfalls,
    suiviWaterfallFiles,
    "Aucun waterfall de contribution disponible pour la trajectoire lexicale.",
    { previewKicker: "Trajectoire lexicale" }
  );

  renderImage(
    resultContainers.suiviMatrixPlot,
    findFile(index, [(path) => path.endsWith("sante/matrice_divergence_jensen_shannon.png")]),
    "Matrice de divergence de Jensen-Shannon"
  );
  makeResultImagePreviewable(
    resultContainers.suiviMatrixPlot,
    "Matrice de divergence de Jensen-Shannon",
    "Trajectoire lexicale"
  );

  await renderJsdCsvFromFile(
    resultContainers.suiviMatrixTable,
    findFile(index, [(path) => path.endsWith("sante/matrice_divergence_jensen_shannon.csv")]),
    {
      mode: "matrix",
      title: "matrice_divergence_jensen_shannon.csv",
      emptyMessage: "La matrice de divergence de Jensen-Shannon est indisponible."
    }
  );

  const suiviWordcloudFiles = findFiles(
    index,
    (path) => path.endsWith(".png") && path.includes("sante/wordclouds/")
  )
    .sort((left, right) => left.path.localeCompare(right.path, undefined, { numeric: true }))
    .map(({ path, file }) => ({
      file,
      title: path
        .replace(/^.*sante\/wordclouds\//, "")
        .replace("_wordcloud.png", "")
        .replaceAll("_", " ")
    }));

  renderImageGallery(
    resultContainers.suiviWordclouds,
    suiviWordcloudFiles,
    "Aucun nuage de mots disponible pour le suivi.",
    { previewKicker: "Trajectoire lexicale" }
  );
}

async function loadCorpusPreview(file) {
  try {
    const text = await file.text();
    const starredMetadata = extractStarredMetadataFromCorpusText(text);
    appState.corpusText = text;
    appState.afcStarredVariablesChoices = starredMetadata.variables;
    appState.corpusStarredDocs = starredMetadata.docs;
    appState.corpusStarredModalitiesByVariable = starredMetadata.modalitiesByVariable;
    const preview = text.slice(0, 4000).trim();
    corpusPreview.textContent = preview || "Le fichier est vide.";
    renderAfcStarredVariablesPickers(document, { resetSelection: true });
    renderSuiviControls(document, { resetSelection: true });
  } catch (error) {
    appState.corpusText = "";
    appState.afcStarredVariablesChoices = [];
    appState.corpusStarredDocs = [];
    appState.corpusStarredModalitiesByVariable = {};
    corpusPreview.textContent = "Impossible de lire un apercu du fichier.";
    renderAfcStarredVariablesPickers(document, { resetSelection: true });
    renderSuiviControls(document, { resetSelection: true });
    log(`[error] Lecture du fichier impossible: ${error.message}`);
  }
}

function syncFieldValue(source, target) {
  if (!source || !target) return;
  if (source instanceof HTMLSelectElement && target instanceof HTMLSelectElement && source.multiple && target.multiple) {
    const selectedValues = new Set(Array.from(source.selectedOptions).map((option) => option.value));
    Array.from(target.options).forEach((option) => {
      option.selected = selectedValues.has(option.value);
    });
    return;
  }
  if (source instanceof HTMLInputElement && target instanceof HTMLInputElement) {
    if (source.type === "checkbox" || source.type === "radio") {
      target.checked = source.checked;
      return;
    }
  }
  if ("value" in target) {
    target.value = source.value;
    return;
  }

  if (source instanceof HTMLElement && target instanceof HTMLElement) {
    target.textContent = source.textContent;
  }
}

function applyDialogValuesToSource() {
  const dialogFields = chdConfigDialogContent.querySelectorAll("[data-source-id]");
  dialogFields.forEach((dialogField) => {
    const source = document.getElementById(dialogField.dataset.sourceId);
    if (!source) return;

    if (dialogField instanceof HTMLSelectElement && source instanceof HTMLSelectElement && dialogField.multiple && source.multiple) {
      const selectedValues = new Set(Array.from(dialogField.selectedOptions).map((option) => option.value));
      Array.from(source.options).forEach((option) => {
        option.selected = selectedValues.has(option.value);
      });
      source.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    if (dialogField instanceof HTMLInputElement && source instanceof HTMLInputElement) {
      if (dialogField.type === "checkbox" || dialogField.type === "radio") {
        source.checked = dialogField.checked;
        if (dialogField.type !== "radio" || dialogField.checked) {
          source.dispatchEvent(new Event("change", { bubbles: true }));
        }
      } else {
        source.value = dialogField.value;
        source.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return;
    }

    if ("value" in dialogField && "value" in source) {
      source.value = dialogField.value;
      source.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
  renderClassificationModeCards(document);
  renderLdaMorphoPickers(document);
}

function applyDialogValues(dialogContent) {
  const dialogFields = dialogContent.querySelectorAll("[data-source-id]");
  dialogFields.forEach((dialogField) => {
    const source = document.getElementById(dialogField.dataset.sourceId);
    if (!source) return;

    if (dialogField instanceof HTMLSelectElement && source instanceof HTMLSelectElement && dialogField.multiple && source.multiple) {
      const selectedValues = new Set(Array.from(dialogField.selectedOptions).map((option) => option.value));
      Array.from(source.options).forEach((option) => {
        option.selected = selectedValues.has(option.value);
      });
      source.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    if (dialogField instanceof HTMLInputElement && source instanceof HTMLInputElement) {
      if (dialogField.type === "checkbox" || dialogField.type === "radio") {
        source.checked = dialogField.checked;
        if (dialogField.type !== "radio" || dialogField.checked) {
          source.dispatchEvent(new Event("change", { bubbles: true }));
        }
      } else {
        source.value = dialogField.value;
        source.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return;
    }

    if ("value" in dialogField && "value" in source) {
      source.value = dialogField.value;
      source.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
  renderClassificationModeCards(document);
  renderLdaMorphoPickers(document);
}

function populateChdConfigDialog() {
  chdConfigDialogContent.innerHTML = "";

  chdConfigSourceCards.forEach((card) => {
    const clone = card.cloneNode(true);
    clone.removeAttribute("data-chd-config-source");

    clone.querySelectorAll("[id]").forEach((element) => {
      const originalId = element.id;
      element.dataset.sourceId = originalId;
      element.id = `${originalId}__dialog`;

      const source = document.getElementById(originalId);
      if (source) {
        syncFieldValue(source, element);
      }
    });

    clone.querySelectorAll("label[for]").forEach((label) => {
      label.htmlFor = `${label.htmlFor}__dialog`;
    });

    chdConfigDialogContent.appendChild(clone);
  });
}

function populateConfigDialog(dialogContent, sourceCards, suffix = "__dialog") {
  dialogContent.innerHTML = "";

  sourceCards.forEach((card) => {
    const clone = card.cloneNode(true);
    clone.removeAttribute("data-chd-config-source");
    clone.removeAttribute("data-simi-config-source");
    clone.removeAttribute("data-suivi-config-source");

    clone.querySelectorAll("[id]").forEach((element) => {
      const originalId = element.id;
      element.dataset.sourceId = originalId;
      element.id = `${originalId}${suffix}`;

      const source = document.getElementById(originalId);
      if (source) {
        syncFieldValue(source, element);
      }
    });

    clone.querySelectorAll("label[for]").forEach((label) => {
      label.htmlFor = `${label.htmlFor}${suffix}`;
    });

    clone.querySelectorAll("input[type='radio'][name]").forEach((radio) => {
      radio.name = `${radio.name}${suffix}`;
    });

    dialogContent.appendChild(clone);
  });
}

function openChdConfigDialog() {
  if (!chdConfigDialog || !chdConfigDialogContent) {
    log("[error] Boîte de dialogue CHD introuvable dans l'interface.");
    return;
  }

  try {
    populateConfigDialog(chdConfigDialogContent, chdConfigSourceCards, "__dialog");
    renderMorphoPickers(chdConfigDialogContent);
    renderAfcStarredVariablesPickers(chdConfigDialogContent);
    renderClassificationModeCards(chdConfigDialogContent);

    if (typeof chdConfigDialog.showModal === "function") {
      chdConfigDialog.showModal();
    } else if (typeof chdConfigDialog.show === "function") {
      chdConfigDialog.show();
    } else {
      chdConfigDialog.setAttribute("open", "");
    }
  } catch (error) {
    log(`[error] Ouverture de la boîte CHD impossible : ${error?.message || String(error)}`);
  }
}

function closeChdConfigDialog() {
  if (chdConfigDialog.open) {
    chdConfigDialog.close();
  }
}

async function openSimiConfigDialog() {
  populateConfigDialog(simiConfigDialogContent, simiConfigSourceCards, "__simi_dialog");
  renderSimiTermsPickers(simiConfigDialogContent);
  if (typeof simiConfigDialog.showModal === "function") {
    simiConfigDialog.showModal();
  }
}

function closeSimiConfigDialog() {
  if (simiConfigDialog.open) {
    simiConfigDialog.close();
  }
}

function openLdaConfigDialog() {
  populateConfigDialog(ldaConfigDialogContent, ldaConfigSourceCards, "__lda_dialog");
  renderLdaMorphoPickers(ldaConfigDialogContent);
  if (typeof ldaConfigDialog.showModal === "function") {
    ldaConfigDialog.showModal();
  }
}

function closeLdaConfigDialog() {
  if (ldaConfigDialog.open) {
    ldaConfigDialog.close();
  }
}

function openSuiviConfigDialog() {
  populateConfigDialog(suiviConfigDialogContent, suiviConfigSourceCards, "__suivi_dialog");
  renderMorphoPickers(suiviConfigDialogContent);
  renderSuiviControls(suiviConfigDialogContent, { resetSelection: false });
  if (typeof suiviConfigDialog.showModal === "function") {
    suiviConfigDialog.showModal();
  }
}

function closeSuiviConfigDialog() {
  if (suiviConfigDialog.open) {
    suiviConfigDialog.close();
  }
}

function createMultimodalCompareAbDialogBoundControl(sourceId, suffix = "__compare_ab_dialog") {
  const source = document.getElementById(sourceId);
  if (!source) return null;
  const clone = source.cloneNode(true);
  clone.dataset.sourceId = sourceId;
  clone.id = `${sourceId}${suffix}`;
  syncFieldValue(source, clone);
  return clone;
}

function createMultimodalCompareAbDialogField(labelText, sourceId) {
  const wrapper = document.createElement("label");
  wrapper.className = "field";
  wrapper.append(document.createTextNode(labelText));
  const control = createMultimodalCompareAbDialogBoundControl(sourceId);
  if (control) {
    wrapper.appendChild(control);
  }
  return wrapper;
}

function createMultimodalCompareAbDialogCheckboxPair(title, leftConfig, rightConfig) {
  const section = document.createElement("div");

  const titleNode = document.createElement("span");
  titleNode.className = "field-label";
  titleNode.textContent = title;
  section.appendChild(titleNode);

  const grid = document.createElement("div");
  grid.className = "form-grid";

  [leftConfig, rightConfig].forEach((config) => {
    const label = document.createElement("label");
    label.className = "checkbox-field";
    const input = createMultimodalCompareAbDialogBoundControl(config.sourceId);
    if (input) {
      label.appendChild(input);
    }
    const text = document.createElement("span");
    text.textContent = config.label;
    label.appendChild(text);
    grid.appendChild(label);
  });

  section.appendChild(grid);
  return section;
}

function getMultimodalComparisonPreviewContainer(side) {
  return side === "b" ? multimodalComparePreviewB : multimodalComparePreviewA;
}

function renderMultimodalComparisonPreview(side) {
  const container = getMultimodalComparisonPreviewContainer(side);
  if (!container) return;

  clearContainer(container);

  const videoFile = getMultimodalComparisonVideoFile(side);
  const source = getMultimodalComparisonSource(side);
  const youtubeUrl = getMultimodalComparisonYoutubeUrl(side);
  const videoId = extractYouTubeVideoId(youtubeUrl);

  if (source?.kind === "youtube") {
    if (!youtubeUrl) {
      container.appendChild(createEmptyState(`Aperçu ${side.toUpperCase()} indisponible tant qu'aucune URL n'est renseignée.`));
      return;
    }
    if (!videoId) {
      container.appendChild(createEmptyState(`Impossible d'afficher l'aperçu ${side.toUpperCase()} : l'URL YouTube n'est pas reconnue.`));
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "multimodal-youtube-embed";
    const iframe = document.createElement("iframe");
    iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}`;
    iframe.title = `Lecteur YouTube comparaison ${side.toUpperCase()}`;
    iframe.loading = "lazy";
    iframe.allow =
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
    iframe.referrerPolicy = "strict-origin-when-cross-origin";
    iframe.allowFullscreen = true;
    wrapper.appendChild(iframe);
    container.appendChild(wrapper);
    return;
  }

  if (source?.kind === "video_file") {
    const nativePath = getResolvedMultimodalComparisonVideoPath(side, videoFile);
    const localUrl = maybeCreateLocalFileUrl(nativePath) || (videoFile ? createObjectUrl(videoFile) : "");
    if (!localUrl) {
      container.appendChild(createEmptyState(`Impossible d'afficher l'aperçu vidéo ${side.toUpperCase()}.`));
      return;
    }
    const video = document.createElement("video");
    video.className = "multimodal-compare-video-preview-player";
    video.src = localUrl;
    video.controls = true;
    video.preload = "metadata";
    video.playsInline = true;
    container.appendChild(video);
    return;
  }

  container.appendChild(createEmptyState(`Aperçu ${side.toUpperCase()} indisponible tant qu'aucune source n'est renseignée.`));
}

function updateMultimodalCompareAbDialogFaceMode(dialogRoot = multimodalCompareAbConfigDialogContent) {
  if (!dialogRoot) return;
  const anatomyModeField = dialogRoot.querySelector('[data-source-id="multimodalMotionAnatomyMode"]');
  const faceModeField = dialogRoot.querySelector('[data-source-id="multimodalMotionFaceAnalysisMode"]');
  if (!(faceModeField instanceof HTMLSelectElement)) return;
  const disableFaceMode = anatomyModeField instanceof HTMLSelectElement && anatomyModeField.value === "corps_entier";
  faceModeField.disabled = disableFaceMode;
  if (disableFaceMode) {
    faceModeField.value = "principal";
  }
}

function populateMultimodalCompareAbConfigDialog() {
  if (!multimodalCompareAbConfigDialogContent) return;
  multimodalCompareAbConfigDialogContent.innerHTML = "";

  const fragment = document.createDocumentFragment();

  const comparisonSection = document.createElement("article");
  comparisonSection.className = "card";
  comparisonSection.innerHTML = "<h3>Comparaison A/B</h3>";
  comparisonSection.appendChild(createMultimodalCompareAbDialogField("Cadence A/B", "multimodalCompareFrameRate"));
  const outputStatus = document.createElement("p");
  outputStatus.className = "readonly-field";
  outputStatus.textContent = `Dossier de sortie : ${getMultimodalComparisonOutputDir()}`;
  comparisonSection.appendChild(outputStatus);
  fragment.appendChild(comparisonSection);

  const audioSection = document.createElement("article");
  audioSection.className = "card";
  audioSection.innerHTML = "<h3>Audio</h3>";
  audioSection.appendChild(createMultimodalCompareAbDialogField("Facteur k des anomalies audio", "multimodalAudioAmplitudeFilterK"));
  const audioHelp = document.createElement("p");
  audioHelp.className = "readonly-field";
  audioHelp.textContent = "Lecture : moyenne ± k écart-type, sur des fenêtres d'1 seconde.";
  audioSection.appendChild(audioHelp);
  fragment.appendChild(audioSection);

  const renderSection = document.createElement("article");
  renderSection.className = "card";
  renderSection.innerHTML = "<h3>Rendu des images</h3>";
  renderSection.appendChild(createMultimodalCompareAbDialogCheckboxPair(
    "Qualité des images",
    { sourceId: "multimodalFrameQualityLow", label: "Définition standard (1024 px)" },
    { sourceId: "multimodalFrameQualityHigh", label: "Très haute définition (1920 px)" }
  ));
  fragment.appendChild(renderSection);

  const motionSection = document.createElement("article");
  motionSection.className = "card";
  motionSection.innerHTML = "<h3>Mouvements</h3>";
  motionSection.appendChild(createMultimodalCompareAbDialogField("Backend anatomique", "multimodalMotionAnatomyBackend"));
  motionSection.appendChild(createMultimodalCompareAbDialogField("Zone d'analyse", "multimodalMotionAnatomyMode"));
  motionSection.appendChild(createMultimodalCompareAbDialogField("Analyse des visages", "multimodalMotionFaceAnalysisMode"));
  fragment.appendChild(motionSection);

  multimodalCompareAbConfigDialogContent.appendChild(fragment);

  const anatomyModeField = multimodalCompareAbConfigDialogContent.querySelector('[data-source-id="multimodalMotionAnatomyMode"]');
  anatomyModeField?.addEventListener("change", () => {
    updateMultimodalCompareAbDialogFaceMode(multimodalCompareAbConfigDialogContent);
  });
  updateMultimodalCompareAbDialogFaceMode(multimodalCompareAbConfigDialogContent);
}

function openMultimodalCompareAbConfigDialog() {
  if (!multimodalCompareAbConfigDialog || !multimodalCompareAbConfigDialogContent) return;
  try {
    populateMultimodalCompareAbConfigDialog();
    if (typeof multimodalCompareAbConfigDialog.showModal === "function") {
      multimodalCompareAbConfigDialog.showModal();
    } else if (typeof multimodalCompareAbConfigDialog.show === "function") {
      multimodalCompareAbConfigDialog.show();
    } else {
      multimodalCompareAbConfigDialog.setAttribute("open", "");
    }
  } catch (error) {
    log(`[error] Ouverture de la boîte de dialogue Comparaison A/B impossible : ${error?.message || String(error)}`);
  }
}

function closeMultimodalCompareAbConfigDialog() {
  if (multimodalCompareAbConfigDialog?.open) {
    multimodalCompareAbConfigDialog.close();
  }
}

function buildExportsIndex(fileList) {
  const entries = fileList.map((file) => ({
    file,
    relativePath: getRelativePath(file),
    normalizedPath: normalizePath(getRelativePath(file))
  }));

  const index = new Map(entries.map((entry) => [entry.normalizedPath, entry.file]));

  return { entries, index };
}

function findFile(index, predicates) {
  for (const [path, file] of index.entries()) {
    if (predicates.some((predicate) => predicate(path))) {
      return file;
    }
  }
  return null;
}

function findFiles(index, predicate) {
  return Array.from(index.entries())
    .filter(([path]) => predicate(path))
    .map(([path, file]) => ({ path, file }));
}

async function renderExports(entries, index) {
  clearObjectUrls();
  appState.chdSegmentsByClass = new Map();
  resetSimiTermsState();

  appState.chdDendrogramFiles = new Map([
    ["iramuteq", findFile(index, [(path) => path.endsWith("dendrogramme_chd.png")])],
    ["factoextra", findFile(index, [(path) => path.endsWith("dendrogramme_chd_factoextra.png")])]
  ]);
  renderSelectableChdDendrogram();

  const chdSegmentsFile = findFile(index, [(path) => path.endsWith("segments_par_classe.txt")]);
  if (chdSegmentsFile) {
    try {
      appState.chdSegmentsByClass = parseSegmentsByClassText(await chdSegmentsFile.text());
    } catch (error) {
      appState.chdSegmentsByClass = new Map();
      log(`[error] Lecture TXT impossible (${chdSegmentsFile.name}): ${error.message}`);
    }
  }

  const chdStatsFile = findFile(index, [(path) => path.endsWith("stats_par_classe.csv")]);
  if (!chdStatsFile) {
    clearContainer(resultContainers.chdStatsTable);
    resultContainers.chdStatsTable.appendChild(
      createEmptyState("Le fichier stats_par_classe.csv est absent du dossier d'exports.")
    );
  } else {
    try {
      const parsedChdStats = parseCsv(await chdStatsFile.text());
      syncSimiTermsChoicesFromChdStats(parsedChdStats);
      renderChdStatsByClass(resultContainers.chdStatsTable, parsedChdStats, {
        title: "stats_par_classe.csv",
        emptyMessage: "Le fichier stats_par_classe.csv est vide."
      });
      renderSimiTermsPickers(document, { resetSelection: true });
    } catch (error) {
      clearContainer(resultContainers.chdStatsTable);
      resultContainers.chdStatsTable.appendChild(createEmptyState("Impossible de lire les statistiques CHD."));
      log(`[error] Lecture CSV impossible (${chdStatsFile.name}): ${error.message}`);
    }
  }

  const concordancierFile = findFile(index, [
    (path) => path.endsWith("segments_par_classe.html"),
    (path) => path.endsWith("concordancier.html"),
    (path) => path.endsWith("concordancier_afc.html")
  ]);

  if (concordancierFile) {
    try {
      renderHtmlFrame(
        resultContainers.chdConcordancier,
        await concordancierFile.text(),
        "Aucun concordancier HTML disponible."
      );
    } catch (error) {
      renderHtmlFrame(resultContainers.chdConcordancier, "", "Impossible de lire le concordancier HTML.");
      log(`[error] Lecture HTML impossible (${concordancierFile.name}): ${error.message}`);
    }
  } else {
    renderHtmlFrame(resultContainers.chdConcordancier, "", "Aucun concordancier HTML disponible.");
  }

  const wordcloudFiles = findFiles(
    index,
    (path) => path.endsWith(".png") && path.startsWith("wordclouds/")
  )
    .sort((left, right) => left.path.localeCompare(right.path, undefined, { numeric: true }))
    .map(({ path, file }) => ({
      file,
      title: path
        .replace(/^.*wordclouds\//, "")
        .replace("_wordcloud.png", "")
        .replace("cluster_", "Classe ")
    }));

  renderImageGallery(
    resultContainers.chdWordclouds,
    wordcloudFiles,
        "Aucun nuage de mots exporté dans wordclouds/.",
    { previewKicker: "CHD" }
  );

  renderImage(
    resultContainers.afcClassesPlot,
    findFile(index, [(path) => path.endsWith("afc/afc_classes.png")]),
    "AFC des classes"
  );

  renderImage(
    resultContainers.afcTermsPlot,
    findFile(index, [(path) => path.endsWith("afc/afc_termes.png")]),
    "AFC des termes"
  );

  renderImage(
    resultContainers.afcVarsPlot,
    findFile(index, [(path) => path.endsWith("afc/afc_variables_etoilees.png")]),
    "AFC des variables etoilees"
  );

  await renderAfcTermsByClass(
    resultContainers.afcTermsTable,
    findFile(index, [(path) => path.endsWith("afc/stats_termes.csv")]),
    {
      title: "stats_termes.csv",
      emptyMessage: "Le fichier afc/stats_termes.csv est absent."
    }
  );

  await renderCsvFromFile(
    resultContainers.afcVarsTable,
    findFile(index, [(path) => path.endsWith("afc/stats_modalites.csv")]),
    {
      title: "stats_modalites.csv",
      emptyMessage: "Le fichier afc/stats_modalites.csv est absent."
    }
  );

  await renderCombinedTables(
    resultContainers.afcEigTable,
    [
      {
        title: "valeurs_propres.csv",
        file: findFile(index, [(path) => path.endsWith("afc/valeurs_propres.csv")])
      },
      {
        title: "valeurs_propres_vars.csv",
        file: findFile(index, [(path) => path.endsWith("afc/valeurs_propres_vars.csv")])
      }
    ],
    "Aucune table de valeurs propres disponible."
  );

  await renderLongitudinalExports(index);

  const ldaWordcloudFiles = findFiles(
    index,
    (path) => path.endsWith(".png") && (path.includes("wordcloud_lda") || path.includes("lda/wordcloud"))
  )
    .sort((left, right) => left.path.localeCompare(right.path, undefined, { numeric: true }))
    .map(({ path, file }) => ({
      file,
      title: path.split("/").pop().replace(".png", "")
    }));

  renderImageGallery(
    resultContainers.ldaWordclouds,
    ldaWordcloudFiles,
    "Aucun nuage LDA détecté dans le dossier chargé.",
    { previewKicker: "LDA" }
  );

  const ldaVisHtmlFile = findFile(index, [
    (path) => path.endsWith("lda/pyldavis.html"),
    (path) => path.endsWith("pyldavis.html")
  ]);
  if (ldaVisHtmlFile) {
    try {
      renderHtmlFrame(
        resultContainers.ldaBubblePlot,
        await ldaVisHtmlFile.text(),
        "Impossible de lire la visualisation pyLDAvis."
      );
    } catch (error) {
      clearContainer(resultContainers.ldaBubblePlot);
      resultContainers.ldaBubblePlot.appendChild(createEmptyState("Impossible de lire la visualisation pyLDAvis."));
      log(`[error] Lecture HTML impossible (${ldaVisHtmlFile.name}): ${error.message}`);
    }
  } else {
    clearContainer(resultContainers.ldaBubblePlot);
    resultContainers.ldaBubblePlot.appendChild(
      createEmptyState("Visualisation pyLDAvis indisponible. Vérifiez que le package Python pyLDAvis est installé.")
    );
  }

  const ldaHeatmapFile = findFile(index, [
    (path) => path.endsWith("lda/heatmap_lda.png"),
    (path) => path.endsWith("/heatmap_lda.png"),
    (path) => path.endsWith("heatmap_lda.png")
  ]);
  if (ldaHeatmapFile) {
    renderImage(resultContainers.ldaHeatmap, ldaHeatmapFile, "Heatmap LDA mots × topics");
    const heatmapImage = resultContainers.ldaHeatmap?.querySelector(".result-image");
    if (heatmapImage instanceof HTMLImageElement) {
      heatmapImage.classList.add("is-clickable");
      heatmapImage.addEventListener("click", () =>
        openImagePreview("Heatmap mots × topics", heatmapImage.src, "LDA")
      );
    }
  } else {
    clearContainer(resultContainers.ldaHeatmap);
    resultContainers.ldaHeatmap.appendChild(
      createEmptyState("Aucune heatmap LDA détectée dans le dossier chargé.")
    );
  }

  const ldaTopTermsFile = findFile(index, [
    (path) => path.endsWith("lda/topic_term_matrix.csv"),
    (path) => path.endsWith("/topic_term_matrix.csv"),
    (path) => path.endsWith("topic_term_matrix.csv"),
    (path) => path.endsWith("lda/top_terms.csv"),
    (path) => path.endsWith("/top_terms.csv"),
    (path) => path.endsWith("top_terms.csv"),
    (path) => path.endsWith("lda/topics.csv"),
    (path) => path.endsWith("/topics.csv") && !path.endsWith("doc_topics.csv") && !path.endsWith("documents_topics.csv")
  ]);
  log(`[info] Fichier LDA retenu pour les mots : ${ldaTopTermsFile?.name || "aucun"}.`);
  await renderLdaBipartiteNetwork(
    resultContainers.ldaNetwork,
    ldaTopTermsFile,
    {
      heading: "Réseau topics × mots",
      emptyMessage: "Aucun export CSV LDA exploitable n'a été trouvé."
    }
  );

  await renderLdaTopTermsMatrix(
    resultContainers.ldaTopTerms,
    ldaTopTermsFile,
    {
      title: "Probabilités mot × topic",
      emptyMessage: "Aucun export CSV de top termes LDA n'a été trouvé."
    }
  );

  await renderLdaTopTermsByTopic(
    resultContainers.ldaDocTopics,
    ldaTopTermsFile,
    {
      heading: "Tableaux par topic",
      title: "Tableaux par topic",
      emptyMessage: "Aucun export CSV de top termes LDA n'a été trouvé."
    }
  );

  const ldaSegmentsFile = findFile(index, [
    (path) => path.endsWith("lda/lda_python_output.json"),
    (path) => path.endsWith("/lda_python_output.json"),
    (path) => path.endsWith("lda_python_output.json"),
    (path) => path.endsWith("lda/segments_topics.csv"),
    (path) => path.endsWith("/segments_topics.csv"),
    (path) => path.endsWith("segments_topics.csv")
  ]);
  await renderLdaTopicSegments(
    resultContainers.ldaSegments,
    ldaSegmentsFile,
    {
      heading: "Segments de texte par topic",
      topTermsFile: ldaTopTermsFile,
      highlightTermsPerTopic: 20,
      emptyMessage: "Aucun export CSV de segments LDA n'a été trouvé."
    }
  );

  clearContainer(resultContainers.ldaTopicWords);

  const similitudeHtmlFile = findFile(index, [
    (path) => path.endsWith(".html") && path.includes("simi"),
    (path) => path.endsWith(".html") && path.includes("simil"),
    (path) => path.endsWith(".png") && path.includes("simi"),
    (path) => path.endsWith(".png") && path.includes("simil")
  ]);

  if (similitudeHtmlFile?.name.endsWith(".html")) {
    try {
      renderHtmlFrame(
        resultContainers.simiGraph,
        await similitudeHtmlFile.text(),
        "Aucun graphe de similitudes exporté."
      );
    } catch (error) {
      renderHtmlFrame(resultContainers.simiGraph, "", "Impossible de lire le graphe HTML.");
      log(`[error] Lecture HTML impossible (${similitudeHtmlFile.name}): ${error.message}`);
    }
  } else if (similitudeHtmlFile) {
    renderImage(resultContainers.simiGraph, similitudeHtmlFile, "Graphe de similitudes");
  } else {
    clearContainer(resultContainers.simiGraph);
    resultContainers.simiGraph.appendChild(createEmptyState("Aucun graphe de similitudes exporté."));
  }

  appState.exportEntries = entries;
  renderResults(entries.map((entry) => entry.relativePath));
}

async function handleExportsFolderSelection(fileList, navigationTarget = "resultats_chd") {
  const files = Array.from(fileList || []);

  if (!files.length) {
    return;
  }

  const firstPath = files[0].virtualRelativePath || files[0].webkitRelativePath || "";
  const folderName = firstPath.split("/")[0] || "exports";
  const { entries, index } = buildExportsIndex(files);

  appState.exportsFolderName = folderName;
  setSidebarRuntimeStatus("Exports charges dans l'application", "success");

  await renderExports(entries, index);
  activateTopTab(navigationTarget);
  if (navigationTarget === "resultats_chd") {
    activateChdSubTab("dendrogramme");
  } else if (navigationTarget === "suivi_longitudinal") {
    activateSuiviSubTab("suivi_indicateurs");
  }
  log(`[info] Dossier d'exports chargé : ${folderName} (${entries.length} fichiers).`);
}

function resetResultPanes() {
  appState.outputDir = null;
  appState.exportsFolderName = null;
  appState.exportEntries = [];
  appState.analysisHistory = [];
  appState.activeAnalysisHistoryId = null;
  appState.chdSegmentsByClass = new Map();
  appState.jsdConcordancierRows = [];
  appState.suiviPresentation = {
    layer: "lexicale_brute",
    emotionLexicon: "",
    hasEmotionProfiles: false,
    hasValenceProfiles: false
  };
  appState.afcTermsZoom = 1;
  appState.simiZoom = 1;
  resetSimiTermsState();
  updateDownloadResultsState();
  renderAnalysisHistory();
  applySuiviPresentation();
  const messages = {
    chdDendrogramme: "Chargez un dossier d'exports pour afficher les dendrogrammes CHD.",
    chdStatsTable: "Chargez un dossier d'exports pour afficher les statistiques CHD.",
    chdConcordancier: "Chargez un dossier d'exports pour afficher le concordancier HTML.",
    chdWordclouds: "Chargez un dossier d'exports pour afficher les nuages de mots.",
    afcClassesPlot: "Chargez un dossier d'exports pour afficher l'AFC des classes.",
    afcTermsPlot: "Chargez un dossier d'exports pour afficher l'AFC des termes.",
    afcTermsTable: "Chargez un dossier d'exports pour afficher la table AFC des termes.",
    afcVarsPlot: "Chargez un dossier d'exports pour afficher les variables etoilees.",
    afcVarsTable: "Chargez un dossier d'exports pour afficher les modalites projetees.",
    afcEigTable: "Chargez un dossier d'exports pour afficher les valeurs propres.",
    suiviMeta: "Chargez un dossier d'exports pour afficher le cadre de la trajectoire lexicale.",
    suiviIndicatorsTable: "Chargez un dossier d'exports pour afficher les indicateurs par entretien.",
    suiviEntropyPlot: "Chargez un dossier d'exports pour afficher la courbe de l'entropie lexicale.",
    suiviRedundancyPlot: "Chargez un dossier d'exports pour afficher la courbe de la redondance relative.",
    suiviEmotionProfilesPlot: "Chargez un dossier d'exports pour afficher les profils émotionnels de la trajectoire.",
    suiviEmotionProfilesTable: "Chargez un dossier d'exports pour afficher la table des profils émotionnels.",
    suiviValenceProfilesPlot: "Chargez un dossier d'exports pour afficher le résumé de valence positive / négative.",
    suiviValenceProfilesTable: "Chargez un dossier d'exports pour afficher la table de valence positive / négative.",
    suiviJsdSuccessivePlot: "Chargez un dossier d'exports pour afficher la divergence de Jensen-Shannon entre séances successives.",
    suiviJsdSuccessiveTable: "Chargez un dossier d'exports pour afficher le tableau des divergences entre séances successives.",
    suiviJsdReferencePlot: "Chargez un dossier d'exports pour afficher la divergence de Jensen-Shannon par rapport à la première séance.",
    suiviJsdReferenceTable: "Chargez un dossier d'exports pour afficher le tableau des divergences par rapport à la première séance.",
    suiviRupturesPlot: "Chargez un dossier d'exports pour afficher la détection explicite des ruptures discursives.",
    suiviRupturesTable: "Chargez un dossier d'exports pour afficher le tableau de détection des ruptures discursives.",
    suiviTermsTable: "Chargez un dossier d'exports pour afficher les termes qui évoluent entre les séances.",
    suiviContributionsTable: "Chargez un dossier d'exports pour afficher les contributions des termes à la divergence de Jensen-Shannon.",
    suiviFrisesEmergences: "Chargez un dossier d'exports pour afficher la frise des émergences de la trajectoire lexicale.",
    suiviDivergentBars: "Chargez un dossier d'exports pour afficher les barres divergentes de la trajectoire lexicale.",
    suiviWaterfalls: "Chargez un dossier d'exports pour afficher les waterfalls de contribution de la trajectoire lexicale.",
    suiviMatrixPlot: "Chargez un dossier d'exports pour afficher la matrice de divergence de Jensen-Shannon.",
    suiviMatrixTable: "Chargez un dossier d'exports pour afficher le tableau de la matrice de divergence de Jensen-Shannon.",
    suiviWordclouds: "Chargez un dossier d'exports pour afficher les nuages de mots de la trajectoire lexicale.",
    ldaBubblePlot: "Chargez un dossier d'exports LDA pour afficher la visualisation pyLDAvis.",
    ldaHeatmap: "Chargez un dossier d'exports LDA pour afficher la heatmap mots × topics.",
    ldaNetwork: "Chargez un dossier d'exports LDA pour afficher le réseau topics × mots.",
    ldaWordclouds: "Chargez un dossier d'exports LDA pour afficher les nuages par topic.",
    ldaTopTerms: "Chargez un dossier d'exports LDA pour afficher le tableau général des probabilités.",
    ldaSegments: "Chargez un dossier d'exports LDA pour afficher les segments de texte par topic.",
    ldaDocTopics: "Chargez un dossier d'exports LDA pour afficher le tableau des mots par topic.",
    ldaTopicWords: "Chargez un dossier d'exports LDA pour afficher le détail des topics.",
    simiGraph: "Vous devez réaliser une CHD avant l'analyse de similitudes."
  };

  Object.entries(resultContainers).forEach(([key, container]) => {
    if (!clearContainer(container)) {
      return;
    }
    container.appendChild(createEmptyState(messages[key]));
  });

  renderAnalysisSteps([]);
  renderAnalysisSummary(null);
  renderZipfChart(null);
  applySimiZoom();
}

async function runMultimodalComparisonCase(side, progressController, progressPlan) {
  const source = getMultimodalComparisonSource(side);
  if (!source?.value) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Source ${side === "b" ? "B" : "A"} manquante.`,
      { isError: true }
    );
    return null;
  }

  const label = getMultimodalComparisonLabel(side);
  const sourceLabel = side === "b" ? "B" : "A";

  const extractionRequest = buildMultimodalComparisonExtractionRequest(side);
  if (!extractionRequest) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Impossible de préparer l'extraction pour la série ${sourceLabel}.`,
      { isError: true }
    );
    return null;
  }
  const extractionResponse = await runMultimodalScript(extractionRequest, {
    title: `Comparaison ${sourceLabel}`,
    message: `Extraction des fichiers pour ${label}...`,
    statusElement: multimodalCompareAbRunStatus,
    actionButton: runMultimodalCompareAbBtn,
    progressController,
    openProgress: false,
    closeProgressOnSuccess: false,
    closeProgressOnError: true,
    progressRange: progressPlan.extraction,
    hydrateAssets: false,
    recordHistory: false,
    plannedStages: [
      `Préparation de la source ${sourceLabel}...`,
      `Téléchargement ou copie locale ${sourceLabel}...`,
      `Extraction MP3 et images ${sourceLabel}...`,
    ],
  });
  if (!extractionResponse) return null;
  const extraction = getMultimodalComparisonExtractionArtifacts(extractionResponse);
  setMultimodalComparisonLatestExtraction(side, extraction);
  if (!String(extraction.framesDirPath || "").trim()) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Aucune séquence d'images extraite pour la série ${sourceLabel}.`,
      { isError: true }
    );
    return null;
  }

  const audioRequest = buildMultimodalComparisonAudioRequest(side, extraction);
  if (!audioRequest) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Impossible de préparer l'analyse audio pour la série ${sourceLabel}.`,
      { isError: true }
    );
    return null;
  }
  const audioResponse = await runMultimodalScript(audioRequest, {
    title: `Comparaison ${sourceLabel}`,
    message: `Analyse audio pour ${label}...`,
    statusElement: multimodalCompareAbRunStatus,
    actionButton: runMultimodalCompareAbBtn,
    progressController,
    openProgress: false,
    closeProgressOnSuccess: false,
    closeProgressOnError: true,
    progressRange: progressPlan.audio,
    hydrateAssets: false,
    recordHistory: false,
    plannedStages: [
      `Préparation audio ${sourceLabel}...`,
      `Transcription Whisper ${sourceLabel}...`,
      `Calcul des indicateurs audio ${sourceLabel}...`,
    ],
  });
  if (!audioResponse) return null;
  const audio = getMultimodalComparisonAudioArtifacts(audioResponse);
  if (!String(audio.segmentsGlobalCsvPath || "").trim()) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Aucun fichier segments_texte_global_complet.csv produit pour la série ${sourceLabel}.`,
      { isError: true }
    );
    return null;
  }

  if (multimodalMotionAnatomyMode?.value !== "corps_entier" && multimodalMotionFaceAnalysisMode?.value === "manuel") {
    progressController?.close();
    const selectionReady = await ensureMultimodalComparisonFaceSelection(side, extraction, label);
    if (!selectionReady) {
      setReadonlyStatus(
        multimodalCompareAbRunStatus,
        `Analyse interrompue pour ${label} : aucune sélection de visage n'a été validée.`,
        { isError: true }
      );
      return null;
    }
    progressController?.open("Comparaison A/B", `Reprise de l'analyse mouvements pour ${label}...`);
    progressController?.set(progressPlan.motion[0], `Reprise de l'analyse mouvements pour ${label}...`);
  }

  const motionRequest = buildMultimodalComparisonMotionRequest(side, extraction);
  if (!motionRequest) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Impossible de lancer l'analyse mouvements pour la série ${sourceLabel} : dossier d'images introuvable.`,
      { isError: true }
    );
    return null;
  }
  const motionResponse = await runMultimodalScript(motionRequest, {
    title: `Comparaison ${sourceLabel}`,
    message: `Analyse des mouvements pour ${label}...`,
    statusElement: multimodalCompareAbRunStatus,
    actionButton: runMultimodalCompareAbBtn,
    progressController,
    openProgress: false,
    closeProgressOnSuccess: false,
    closeProgressOnError: true,
    progressRange: progressPlan.motion,
    hydrateAssets: false,
    recordHistory: false,
    plannedStages: [
      `Préparation des images ${sourceLabel}...`,
      `Optical flow ${sourceLabel}...`,
      `Agrégation mouvements ${sourceLabel}...`,
    ],
  });
  if (!motionResponse) return null;
  const motion = getMultimodalComparisonMotionArtifacts(motionResponse);
  if (!String(motion.framesCsvPath || "").trim()) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Aucun CSV mouvements_frames_complet.csv produit pour la série ${sourceLabel}.`,
      { isError: true }
    );
    return null;
  }

  const alignRequest = buildMultimodalComparisonAlignRequest(side, extraction, audio, motion);
  if (!alignRequest) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Impossible de lancer l'alignement pour la série ${sourceLabel}.`,
      { isError: true }
    );
    return null;
  }
  const alignResponse = await runMultimodalScript(alignRequest, {
    title: `Comparaison ${sourceLabel}`,
    message: `Alignement multimodal pour ${label}...`,
    statusElement: multimodalCompareAbRunStatus,
    actionButton: runMultimodalCompareAbBtn,
    progressController,
    openProgress: false,
    closeProgressOnSuccess: false,
    closeProgressOnError: true,
    progressRange: progressPlan.align,
    hydrateAssets: false,
    recordHistory: false,
    plannedStages: [
      `Projection des segments ${sourceLabel}...`,
      `Projection des mouvements ${sourceLabel}...`,
      `CSV synchronisé ${sourceLabel}...`,
    ],
  });
  if (!alignResponse) return null;
  const align = getMultimodalComparisonAlignmentArtifacts(alignResponse);
  if (!String(align.alignedSegmentsCsvPath || "").trim()) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Aucun fichier segments_texte_sync_complet.csv produit pour la série ${sourceLabel}.`,
      { isError: true }
    );
    return null;
  }

  return {
    side,
    label,
    source,
    extraction,
    audio,
    motion,
    align,
  };
}

async function runMultimodalComparisonAbPipeline() {
  const sourceA = getMultimodalComparisonSource("a");
  const sourceB = getMultimodalComparisonSource("b");
  if (!sourceA?.value || !sourceB?.value) {
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      "Renseigne d'abord une source A et une source B.",
      { isError: true }
    );
    return;
  }

  setMultimodalComparisonAbRunning(true);
  if (appState.multimodalComparisonAB) {
    appState.multimodalComparisonAB.result = null;
  }
  renderMultimodalWorkspace();
  activateMultimodalSubTab("multimodale_comparaison_ab");

  multimodalProgression.open("Comparaison A/B", "Préparation des deux séries...");
  multimodalProgression.set(1, "Préparation de la comparaison A/B...");
  await waitForNextPaintFrame();

  try {
    const caseA = await runMultimodalComparisonCase("a", multimodalProgression, {
      extraction: [2, 14],
      audio: [14, 24],
      motion: [24, 38],
      align: [38, 48],
    });
    if (!caseA) {
      multimodalProgression.close();
      return;
    }

    const caseB = await runMultimodalComparisonCase("b", multimodalProgression, {
      extraction: [48, 60],
      audio: [60, 70],
      motion: [70, 84],
      align: [84, 94],
    });
    if (!caseB) {
      multimodalProgression.close();
      return;
    }

    const comparisonRequest = buildMultimodalComparisonAbRequest(caseA, caseB);
    if (!comparisonRequest) {
      setReadonlyStatus(
        multimodalCompareAbRunStatus,
        "Impossible de construire la comparaison A/B : CSV synchronisés manquants.",
        { isError: true }
      );
      multimodalProgression.close();
      return;
    }

    const comparisonResponse = await runMultimodalScript(comparisonRequest, {
      title: "Comparaison A/B",
      message: "Construction de la comparaison finale...",
      statusElement: multimodalCompareAbRunStatus,
      actionButton: runMultimodalCompareAbBtn,
      progressController: multimodalProgression,
      openProgress: false,
      closeProgressOnSuccess: false,
      closeProgressOnError: true,
      progressRange: [94, 100],
      hydrateAssets: false,
      recordHistory: false,
      plannedStages: [
        "Normalisation temporelle A/B...",
        "Calcul des écarts d'indicateurs...",
        "Écriture des exports de comparaison...",
      ],
    });
    if (!comparisonResponse) {
      multimodalProgression.close();
      return;
    }

    hydrateMultimodalComparisonAbAssets(comparisonResponse, { caseA, caseB });
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      `Terminé. Exports écrits dans : ${comparisonResponse.outputDir}`
    );
    multimodalProgression.set(100, "Comparaison A/B terminée.");
    setTimeout(() => multimodalProgression.close(), 700);
    renderMultimodalWorkspace();
  } catch (error) {
    log(`[error] ${error?.message || String(error)}`);
    setReadonlyStatus(
      multimodalCompareAbRunStatus,
      error?.message || String(error),
      { isError: true }
    );
    multimodalProgression.set(100, "Comparaison A/B interrompue.");
    multimodalProgression.close();
  } finally {
    setMultimodalComparisonAbRunning(false);
    renderMultimodalWorkspace();
  }
}

topNavLinks.forEach((link) => {
  link.addEventListener("click", () => {
    activateTopTab(link.dataset.tabTarget);
  });
});

document.querySelectorAll("[data-open-chd-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    openChdConfigDialog();
  });
});

document.querySelectorAll("[data-open-simi-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    void openSimiConfigDialog();
  });
});

document.querySelectorAll("[data-open-lda-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    openLdaConfigDialog();
  });
});

document.querySelectorAll("[data-open-suivi-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    openSuiviConfigDialog();
  });
});

closeChdDialogBtn.addEventListener("click", () => {
  closeChdConfigDialog();
});

launchChdDialogBtn.addEventListener("click", () => {
  applyDialogValuesToSource();
  closeChdConfigDialog();
  activateTopTab("analyse");
  log("[info] Lancement de l'analyse CHD depuis la boite de dialogue.");
  void startAnalysis();
});

closeSimiDialogBtn.addEventListener("click", () => {
  closeSimiConfigDialog();
});

launchSimiDialogBtn.addEventListener("click", () => {
  applyDialogValues(simiConfigDialogContent);
  renderSimiTermsPickers(document);
  closeSimiConfigDialog();
  activateTopTab("analyse");
  log("[info] Lancement de l'analyse de similitudes depuis la boite de dialogue.");
  void startAnalysis("simi");
});

closeLdaDialogBtn.addEventListener("click", () => {
  closeLdaConfigDialog();
});

closeSuiviDialogBtn?.addEventListener("click", () => {
  closeSuiviConfigDialog();
});

closeMultimodalCompareAbDialogBtn?.addEventListener("click", () => {
  closeMultimodalCompareAbConfigDialog();
});

applyMultimodalCompareAbDialogBtn?.addEventListener("click", () => {
  applyDialogValues(multimodalCompareAbConfigDialogContent);
  closeMultimodalCompareAbConfigDialog();
  renderMultimodalWorkspace();
});

closeImagePreviewBtn?.addEventListener("click", () => {
  closeImagePreview();
});

imagePreviewPrevBtn?.addEventListener("click", () => {
  navigateImagePreview(-1);
});

imagePreviewNextBtn?.addEventListener("click", () => {
  navigateImagePreview(1);
});

imagePreviewDialog?.addEventListener("keydown", (event) => {
  if (!imagePreviewDialog.open) return;
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    navigateImagePreview(-1);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    navigateImagePreview(1);
  }
});

closeMultimodalFaceSelectionBtn?.addEventListener("click", () => {
  closeMultimodalFaceSelectionDialog();
});

multimodalFaceSelectionDialog?.addEventListener("close", () => {
  const session = multimodalFaceSelectionSession;
  if (multimodalFaceSelectionStage) {
    multimodalFaceSelectionStage.innerHTML = "";
  }
  multimodalFaceSelectionSession = null;
  if (session && !session.handled && typeof session.onClose === "function") {
    session.onClose();
  }
});

resetMultimodalFaceSelectionBtn?.addEventListener("click", () => {
  multimodalFaceSelectionDraft = null;
  const sourceItems = getActiveMultimodalFaceSelectionSessionSources();
  const activeSelection = getActiveMultimodalFaceSelectionSessionSelection();
  const sourceIndex = Number(multimodalFaceSelectionSource?.value || Number(activeSelection?.sourceIndex) || 0);
  const safeIndex = Math.max(0, Math.min(sourceItems.length - 1, sourceIndex));
  const sourceItem = sourceItems[safeIndex] || null;
  if (sourceItem) {
    renderMultimodalFaceSelectionSurface(sourceItem);
  } else if (multimodalFaceSelectionCoords) {
    multimodalFaceSelectionCoords.textContent = "Aucune zone dessinée.";
  }
});

multimodalFaceSelectionSource?.addEventListener("change", () => {
  const sourceItems = getActiveMultimodalFaceSelectionSessionSources();
  const sourceIndex = Number(multimodalFaceSelectionSource.value || 0);
  const safeIndex = Math.max(0, Math.min(sourceItems.length - 1, sourceIndex));
  const sourceItem = sourceItems[safeIndex] || null;
  multimodalFaceSelectionDraft = null;
  if (sourceItem) {
    renderMultimodalFaceSelectionSurface(sourceItem);
  } else if (multimodalFaceSelectionCoords) {
    multimodalFaceSelectionCoords.textContent = "Aucune zone dessinée.";
  }
});

saveMultimodalFaceSelectionBtn?.addEventListener("click", () => {
  const session = multimodalFaceSelectionSession;
  const sourceItems = getActiveMultimodalFaceSelectionSessionSources();
  const sourceIndex = Number(multimodalFaceSelectionSource?.value || 0);
  const safeIndex = Math.max(0, Math.min(sourceItems.length - 1, sourceIndex));
  const sourceItem = sourceItems[safeIndex] || null;
  if (!sourceItem || !Array.isArray(multimodalFaceSelectionDraft) || multimodalFaceSelectionDraft.length !== 4) {
    if (multimodalFaceSelectionCoords) {
      multimodalFaceSelectionCoords.textContent = "Dessine d'abord un rectangle sur le visage.";
    }
    return;
  }
  const selection = {
    sourceName: sourceItem.sourceName || sourceItem.name || "image",
    sourceIndex: safeIndex,
    box: [...multimodalFaceSelectionDraft],
  };
  if (session) {
    session.selection = selection;
    session.handled = true;
    if (typeof session.onSave === "function") {
      session.onSave(selection);
    }
  } else {
    appState.multimodalSelectedFaceSelection = selection;
  }
  closeMultimodalFaceSelectionDialog();
  renderMultimodalWorkspace();
});

multimodalSelectFaceBtn?.addEventListener("click", () => {
  openMultimodalFaceSelectionDialog();
});

multimodalClearFaceSelectionBtn?.addEventListener("click", () => {
  clearMultimodalFaceSelection();
});

closeTermSegmentsBtn?.addEventListener("click", () => {
  closeTermSegmentsDialog();
});

termSegmentsDialog?.addEventListener("close", () => {
  setTermSegmentsExportState();
  setTermChartExportState();
});

buildSubcorpusBtn?.addEventListener("click", () => {
  void saveCurrentSubcorpus();
});

saveChi2PngBtn?.addEventListener("click", () => {
  void saveCurrentChi2Chart();
});

chdTermContextMenu?.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const actionButton = target.closest("[data-chd-term-action]");
  if (!actionButton) return;
  event.preventDefault();
  void invokeChdAction(actionButton.getAttribute("data-chd-term-action") || "");
});

simiZoomInBtn?.addEventListener("click", () => {
  setSimiZoom(appState.simiZoom + 0.2);
});

simiZoomOutBtn?.addEventListener("click", () => {
  setSimiZoom(appState.simiZoom - 0.2);
});

simiZoomResetBtn?.addEventListener("click", () => {
  setSimiZoom(1);
});

afcTermsZoomInBtn?.addEventListener("click", () => {
  setAfcTermsZoom(appState.afcTermsZoom + 0.2);
});

afcTermsZoomOutBtn?.addEventListener("click", () => {
  setAfcTermsZoom(appState.afcTermsZoom - 0.2);
});

afcTermsZoomResetBtn?.addEventListener("click", () => {
  setAfcTermsZoom(1);
});

launchLdaDialogBtn.addEventListener("click", () => {
  applyDialogValues(ldaConfigDialogContent);
  closeLdaConfigDialog();
  activateTopTab("analyse");
  log("[info] Lancement de l'analyse LDA depuis la boite de dialogue.");
  void startAnalysis("lda");
});

launchSuiviDialogBtn?.addEventListener("click", () => {
  applyDialogValues(suiviConfigDialogContent);
  renderMorphoPickers(document);
  renderSuiviControls(document, { resetSelection: false });
  closeSuiviConfigDialog();
  activateTopTab("analyse");
  log("[info] Lancement de la trajectoire lexicale depuis la boite de dialogue.");
  void startAnalysis("suivi");
});

suiviVariable?.addEventListener("change", () => {
  renderSuiviControls(document, { resetSelection: true });
});

document.getElementById("suiviAnalysisLayer")?.addEventListener("change", () => {
  renderSuiviControls(document, { resetSelection: false });
});

document.getElementById("suiviEmotionLexicon")?.addEventListener("change", () => {
  renderSuiviControls(document, { resetSelection: false });
});

suiviFilterVariable?.addEventListener("change", () => {
  renderSuiviControls(document, { resetSelection: true });
});

suiviFilterModalite?.addEventListener("change", () => {
  renderSuiviControls(document, { resetSelection: true });
});

document.getElementById("suiviChronologyOrder")?.addEventListener("change", () => {
  renderSuiviControls(document, { resetSelection: false });
});

[
  "dictionarySource",
  "useLemmas",
  "morphoFilter",
  "posKeep",
  "excludeEtre",
  "keepUnknownForms"
].forEach((id) => {
  document.getElementById(id)?.addEventListener("change", () => {
    renderSuiviControls(document, { resetSelection: false });
  });
});

suiviSelectAllBtn?.addEventListener("click", () => {
  if (!(suiviInterviewsSelect instanceof HTMLSelectElement)) return;
  Array.from(suiviInterviewsSelect.options).forEach((option) => {
    option.selected = true;
  });
  updateSuiviSummary(document);
});

suiviClearAllBtn?.addEventListener("click", () => {
  if (!(suiviInterviewsSelect instanceof HTMLSelectElement)) return;
  Array.from(suiviInterviewsSelect.options).forEach((option) => {
    option.selected = false;
  });
  updateSuiviSummary(document);
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const sourceId = target.dataset.sourceId || target.id;
  if (!["suiviVariable", "suiviFilterVariable", "suiviFilterModalite", "suiviChronologyOrder", "suiviAnalysisLayer", "suiviEmotionLexicon"].includes(sourceId)) {
    return;
  }

  const dialogScope = target.closest(".dialog-body");
  if (!dialogScope || !dialogScope.querySelector("[data-source-id='suiviVariable']")) {
    return;
  }

  renderSuiviControls(dialogScope, {
    resetSelection: !["suiviChronologyOrder", "suiviAnalysisLayer", "suiviEmotionLexicon"].includes(sourceId)
  });
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.matches("[data-simi-top-terms-input]")) return;

  const card = target.closest("[data-simi-config-card]");
  if (card) {
    renderSimiTermsPicker(card, { resetSelection: true });
  }
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const suiviActionButton = target.closest("button");
  const suiviSourceId = suiviActionButton?.dataset.sourceId || suiviActionButton?.id || "";
  if (suiviSourceId === "suiviSelectAllBtn" || suiviSourceId === "suiviClearAllBtn") {
    const dialogScope = suiviActionButton?.closest(".dialog-body");
    if (dialogScope && dialogScope.querySelector("[data-source-id='suiviInterviewsSelect']")) {
      const interviewsSelect = getScopedSourceElement(dialogScope, "suiviInterviewsSelect");
      if (interviewsSelect instanceof HTMLSelectElement) {
        Array.from(interviewsSelect.options).forEach((option) => {
          option.selected = suiviSourceId === "suiviSelectAllBtn";
        });
      }
    }
    return;
  }

  const addButton = target.closest("[data-morpho-add-btn]");
  if (!addButton) return;

  const card = addButton.closest("[data-chd-morpho-card]");
  if (!card) return;

  const hiddenInput = card.querySelector("[data-morpho-selected-input]");
  const select = card.querySelector("[data-morpho-available-select]");
  if (!hiddenInput || !select || !select.value) return;

  const selected = splitCsvValues(hiddenInput.value).map((value) => value.toUpperCase());
  if (!selected.includes(select.value)) {
    hiddenInput.value = [...selected, select.value].join(", ");
  }
  renderMorphoPicker(card);
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const addButton = target.closest("[data-lda-morpho-add-btn]");
  if (!addButton) return;

  const card = addButton.closest("[data-lda-morpho-card]");
  if (!card) return;

  const hiddenInput = card.querySelector("[data-lda-morpho-selected-input]");
  const select = card.querySelector("[data-lda-morpho-available-select]");
  if (!hiddenInput || !select || !select.value) return;

  const selected = splitCsvValues(hiddenInput.value).map((value) => value.toUpperCase());
  if (!selected.includes(select.value)) {
    hiddenInput.value = [...selected, select.value].join(", ");
  }
  renderLdaMorphoPicker(card);
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.matches("[data-morpho-available-select]")) return;

  const card = target.closest("[data-chd-morpho-card]");
  if (card) {
    renderMorphoPicker(card);
  }
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const addButton = target.closest("[data-afc-starred-add-btn]");
  if (!addButton) return;

  const card = addButton.closest("[data-afc-starred-variables-card]");
  if (!card) return;

  const hiddenInput = card.querySelector("[data-afc-starred-selected-input]");
  const select = card.querySelector("[data-afc-starred-available-select]");
  if (!hiddenInput || !select || !select.value) return;

  const selected = splitCsvValues(hiddenInput.value).map((value) => normalizeStarredVariableName(value));
  const nextValue = normalizeStarredVariableName(select.value);
  if (!selected.some((value) => value.toLowerCase() === nextValue.toLowerCase())) {
    hiddenInput.value = [...selected, nextValue].join(", ");
  }
  renderAfcStarredVariablesPicker(card);
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.matches("[data-lda-morpho-available-select]")) return;

  const card = target.closest("[data-lda-morpho-card]");
  if (card) {
    renderLdaMorphoPicker(card);
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.matches("[data-classification-radio]")) return;
  if (target instanceof HTMLInputElement && !target.checked) return;

  const card = target.closest("[data-classification-mode-card]");
  if (!card) return;

  const hiddenInput = card.querySelector("#classificationMode, [data-source-id='classificationMode']");
  if (!hiddenInput) return;

  hiddenInput.value = target.value === "double" ? "double" : "simple";
  renderClassificationModeCard(card);
});

chdSubNavLinks.forEach((link) => {
  link.addEventListener("click", () => {
    activateChdSubTab(link.dataset.subtabTarget);
  });
});

ldaSubNavLinks.forEach((link) => {
  link.addEventListener("click", () => {
    activateLdaSubTab(link.dataset.ldaSubtabTarget);
  });
});

suiviSubNavLinks.forEach((link) => {
  link.addEventListener("click", () => {
    activateSuiviSubTab(link.dataset.suiviSubtabTarget);
  });
});

multimodalSubNavLinks.forEach((link) => {
  link.addEventListener("click", () => {
    activateMultimodalSubTab(link.dataset.multimodalSubtabTarget);
  });
});

motionResultTabLinks.forEach((link) => {
  link.addEventListener("click", () => {
    activateMotionResultTab(link.dataset.motionResultTarget);
  });
});

helpSubNavLinks.forEach((link) => {
  link.addEventListener("click", () => {
    activateHelpSubTab(link.dataset.helpSubtabTarget);
  });
});

enforceExclusiveCheckboxPair(multimodalFrameRate1, multimodalFrameRate25);
enforceExclusiveCheckboxPair(multimodalFrameQualityLow, multimodalFrameQualityHigh);

chdDendrogramSelect.addEventListener("change", () => {
  renderSelectableChdDendrogram();
});

window.addEventListener("resize", () => {
  syncDendrogramSizing();
  applyAfcTermsZoom();
});

importCorpusBtn.addEventListener("click", () => {
  corpusFileInput.value = "";
  corpusFileInput.click();
});

annotationImportBtn?.addEventListener("click", () => {
  annotationImportCsv?.click();
});

multimodalPickCookiesBtn?.addEventListener("click", () => {
  if (!multimodalCookiesFile) return;
  multimodalCookiesFile.value = "";
  multimodalCookiesFile.click();
});

multimodalPickAudioBtn?.addEventListener("click", () => {
  if (!multimodalAudioFile) return;
  multimodalAudioFile.value = "";
  multimodalAudioFile.click();
});

multimodalPickVideoBtn?.addEventListener("click", () => {
  if (!multimodalVideoFile) return;
  multimodalVideoFile.value = "";
  multimodalVideoFile.click();
});

multimodalComparePickVideoABtn?.addEventListener("click", () => {
  if (!multimodalCompareVideoFileA) return;
  multimodalCompareVideoFileA.value = "";
  multimodalCompareVideoFileA.click();
});

multimodalComparePickVideoBBtn?.addEventListener("click", () => {
  if (!multimodalCompareVideoFileB) return;
  multimodalCompareVideoFileB.value = "";
  multimodalCompareVideoFileB.click();
});

multimodalCompareSelectFaceABtn?.addEventListener("click", async () => {
  await openMultimodalComparisonFaceSelectionDialog("a");
});

multimodalCompareSelectFaceBBtn?.addEventListener("click", async () => {
  await openMultimodalComparisonFaceSelectionDialog("b");
});

multimodalCompareClearFaceABtn?.addEventListener("click", () => {
  clearMultimodalComparisonFaceSelection("a");
});

multimodalCompareClearFaceBBtn?.addEventListener("click", () => {
  clearMultimodalComparisonFaceSelection("b");
});

multimodalComparePickOutputDirBtn?.addEventListener("click", async () => {
  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    setReadonlyStatus(multimodalCompareOutputDirStatus, "Le choix du dossier A/B n'est disponible que dans l'application Tauri.", { isError: true });
    return;
  }
  try {
    const selectedPath = await tauriInvoke("pick_output_directory");
    if (appState.multimodalComparisonAB && selectedPath) {
      appState.multimodalComparisonAB.outputDir = String(selectedPath).trim();
    }
    renderMultimodalWorkspace();
  } catch (error) {
    setReadonlyStatus(multimodalCompareOutputDirStatus, error?.message || String(error), { isError: true });
  }
});

multimodalCompareAbToggleSettingsBtn?.addEventListener("click", () => {
  openMultimodalCompareAbConfigDialog();
});

multimodalPickOutputDirBtn?.addEventListener("click", async () => {
  const tauriInvoke = getTauriInvoke();
  if (!tauriInvoke) {
    setReadonlyStatus(multimodalOutputDirStatus, "Le choix de dossier n'est disponible que dans l'application Tauri.", { isError: true });
    return;
  }
  try {
    const selectedPath = await tauriInvoke("pick_output_directory");
    if (selectedPath) {
      appState.multimodalOutputDir = String(selectedPath).trim();
    }
    renderMultimodalWorkspace();
  } catch (error) {
    setReadonlyStatus(multimodalOutputDirStatus, error?.message || String(error), { isError: true });
  }
});

multimodalAudioImportShortcutBtn?.addEventListener("click", () => {
  if (!multimodalAudioFile) return;
  multimodalAudioFile.value = "";
  multimodalAudioFile.click();
});

multimodalImagesImportShortcutBtn?.addEventListener("click", () => {
  if (!multimodalImagesFiles) return;
  multimodalImagesFiles.value = "";
  multimodalImagesFiles.click();
});

multimodalAlignAudioShortcutBtn?.addEventListener("click", () => {
  activateMultimodalSubTab("multimodale_audio");
  revealMultimodalElement(multimodalAudioPausesPlot || runMultimodalAudioBtn);
});

multimodalAlignImageShortcutBtn?.addEventListener("click", () => {
  activateMultimodalSubTab("multimodale_mouvements");
  revealMultimodalElement(runMultimodalMotionBtn);
});

multimodalPickSegmentsBtn?.addEventListener("click", () => {
  if (!multimodalSegmentsFile) return;
  multimodalSegmentsFile.value = "";
  multimodalSegmentsFile.click();
});

multimodalYoutubeUrl?.addEventListener("input", () => {
  renderMultimodalWorkspace();
});

multimodalCompareYoutubeUrlA?.addEventListener("input", () => {
  resetMultimodalComparisonSourceRuntime("a", { rerender: false });
  renderMultimodalWorkspace();
});

multimodalCompareYoutubeUrlB?.addEventListener("input", () => {
  resetMultimodalComparisonSourceRuntime("b", { rerender: false });
  renderMultimodalWorkspace();
});

multimodalCompareFrameRate?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

[
  multimodalCompareStartHoursA,
  multimodalCompareStartMinutesA,
  multimodalCompareStartSecondsA,
  multimodalCompareEndHoursA,
  multimodalCompareEndMinutesA,
  multimodalCompareEndSecondsA,
  multimodalCompareStartHoursB,
  multimodalCompareStartMinutesB,
  multimodalCompareStartSecondsB,
  multimodalCompareEndHoursB,
  multimodalCompareEndMinutesB,
  multimodalCompareEndSecondsB,
].forEach((input) => {
  input?.addEventListener("input", () => {
    const side = [
      multimodalCompareStartHoursB,
      multimodalCompareStartMinutesB,
      multimodalCompareStartSecondsB,
      multimodalCompareEndHoursB,
      multimodalCompareEndMinutesB,
      multimodalCompareEndSecondsB,
    ].includes(input)
      ? "b"
      : "a";
    resetMultimodalComparisonSourceRuntime(side, { rerender: false });
    renderMultimodalWorkspace();
  });
});

multimodalCookiesFile?.addEventListener("change", async () => {
  await persistSelectedMultimodalFile("cookies", multimodalCookiesFile, multimodalCookiesStatus);
});

multimodalAudioFile?.addEventListener("change", async () => {
  await persistSelectedMultimodalFile("audio", multimodalAudioFile, multimodalAudioStatus);
});

multimodalVideoFile?.addEventListener("change", async () => {
  if (getSelectedFile(multimodalVideoFile)) {
    appState.multimodalSelectedImageFiles = [];
    appState.multimodalLocalPaths.imagesDir = "";
    appState.multimodalImagePaths = [];
  }
  await persistSelectedMultimodalFile("video", multimodalVideoFile, multimodalVideoStatus);
});

multimodalCompareVideoFileA?.addEventListener("change", async () => {
  await persistSelectedMultimodalComparisonVideo("a");
});

multimodalCompareVideoFileB?.addEventListener("change", async () => {
  await persistSelectedMultimodalComparisonVideo("b");
});

multimodalSegmentsFile?.addEventListener("change", async () => {
  const selectedFile = getSelectedMultimodalSegmentsFile();
  let segmentsCsvIsValid = false;
  if (selectedFile) {
    try {
      appState.multimodalSegmentsPreviewParsed = parseCsv(await selectedFile.text());
      segmentsCsvIsValid = isValidAlignmentSegmentsSelection(selectedFile, appState.multimodalSegmentsPreviewParsed);
    } catch (_error) {
      appState.multimodalSegmentsPreviewParsed = null;
    }
  } else {
    appState.multimodalSegmentsPreviewParsed = null;
  }
  await persistSelectedMultimodalFile("segments", multimodalSegmentsFile, multimodalSegmentsStatus);
  if (selectedFile && !segmentsCsvIsValid) {
    setMultimodalInputError(
      "segments",
      isAnomalyOnlySegmentsFile(selectedFile)
        ? "Le CSV choisi est segments_texte_anomalies_complet.csv. Pour Alignement, charge segments_texte_global_complet.csv."
        : "Le CSV choisi n'est pas un fichier de segments texte valide. Charge segments_texte_global_complet.csv avec les colonnes start_sec, end_sec et text."
    );
  } else {
    setMultimodalInputError("segments", "");
  }
  renderMultimodalWorkspace();
  renderMultimodalAlignmentResults();
});

multimodalImagesFiles?.addEventListener("change", async () => {
  appState.multimodalSelectedImageFiles = Array.from(multimodalImagesFiles.files || []).sort((left, right) =>
    naturalCompareValues(left?.name || "", right?.name || "")
  );
  clearMultimodalFaceSelection({ rerender: false });
  await persistSelectedMultimodalImages();
});

multimodalExtractMp4?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

multimodalExtractMp3?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

multimodalExtractWav?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

multimodalExtractSegments?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

multimodalExtractImages?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

multimodalAlignOverlayImages?.addEventListener("change", () => {
  renderMultimodalWorkspace();
  renderMultimodalAlignmentResults();
});

multimodalAlignOverlaySegments?.addEventListener("change", () => {
  renderMultimodalWorkspace();
  renderMultimodalAlignmentResults();
});

multimodalAlignOverlayAudio?.addEventListener("change", () => {
  renderMultimodalWorkspace();
  renderMultimodalAlignmentResults();
});

multimodalAlignImageView?.addEventListener("change", () => {
  renderMultimodalAlignmentResults();
});

multimodalAlignTimelineScale?.addEventListener("change", () => {
  renderMultimodalAlignmentResults();
});

multimodalAlignCurveMode?.addEventListener("change", () => {
  renderMultimodalAlignmentResults();
});

multimodalMotionAnatomyMode?.addEventListener("change", () => {
  if (multimodalMotionFaceAnalysisMode) {
    multimodalMotionFaceAnalysisMode.disabled = multimodalMotionAnatomyMode?.value === "corps_entier";
    if (multimodalMotionFaceAnalysisMode.disabled) {
      multimodalMotionFaceAnalysisMode.value = "principal";
    }
  }
  renderMultimodalWorkspace();
});

multimodalMotionAnatomyBackend?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

multimodalMotionFaceAnalysisMode?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

multimodalIntervalMode?.addEventListener("change", () => {
  renderMultimodalWorkspace();
});

[
  multimodalExtractStartHours,
  multimodalExtractStartMinutes,
  multimodalExtractStartSeconds,
  multimodalExtractEndHours,
  multimodalExtractEndMinutes,
  multimodalExtractEndSeconds,
].forEach((input) => {
  input?.addEventListener("input", () => {
    renderMultimodalWorkspace();
  });
});

runMultimodalYtdlpBtn?.addEventListener("click", async () => {
  multimodalProgression.open("Export multimodal", "Initialisation de l'export des fichiers...");
  multimodalProgression.set(1, "Préparation de la demande d'export...");

  const extractionRequest = buildMultimodalYtdlpArgs();
  const wantsSegments = shouldPrepareMultimodalTimestampedSegments();
  const initialAudioRequest = wantsSegments ? buildMultimodalAudioArgs() : null;

  if (!extractionRequest && !initialAudioRequest) {
    log("[error] Sélectionnez une source multimodale puis cochez au moins une sortie à préparer.");
    setReadonlyStatus(multimodalYtdlpRunStatus, "Sélectionnez une source multimodale puis cochez au moins une sortie à préparer.", { isError: true });
    multimodalProgression.close();
    return;
  }

  let extractionResponse = null;
  const extractionRange = wantsSegments ? [4, 72] : [4, 96];
  const segmentsRange = extractionRequest ? [72, 96] : [4, 96];
  if (extractionRequest) {
    extractionResponse = await runMultimodalScript(extractionRequest, {
      title: "Préparation multimodale",
      message: "Préparation des fichiers cochés en cours...",
      statusElement: multimodalYtdlpRunStatus,
      actionButton: runMultimodalYtdlpBtn,
      progressController: multimodalProgression,
      openProgress: false,
      closeProgressOnSuccess: false,
      closeProgressOnError: true,
      progressRange: extractionRange,
      plannedStages: [
        "Préparation de la source vidéo et des cookies...",
        "Téléchargement ou découpage de l'intervalle demandé...",
        "Normalisation et conversions demandées...",
        "Extraction des pistes audio demandées...",
        "Extraction des images si cochée..."
      ],
    });
    if (!extractionResponse) {
      return;
    }
  }

  if (wantsSegments) {
    const audioRequest = buildMultimodalAudioArgs();
    if (!audioRequest) {
      setReadonlyStatus(
        multimodalYtdlpRunStatus,
        "Impossible de préparer les segments horodatés : aucune source audio exploitable n'est disponible.",
        { isError: true }
      );
      multimodalProgression.close();
      return;
    }

    multimodalProgression.set(segmentsRange[0], "Préparation de l'export des segments horodatés...");
    const audioResponse = await runMultimodalScript(audioRequest, {
      title: "Préparation des segments horodatés",
      message: "Transcription et export des segments avec timestamp en cours...",
      statusElement: multimodalYtdlpRunStatus,
      actionButton: runMultimodalYtdlpBtn,
      progressController: multimodalProgression,
      openProgress: false,
      closeProgressOnSuccess: false,
      closeProgressOnError: true,
      progressRange: segmentsRange,
      plannedStages: [
        "Préparation de la source audio...",
        "Découpage sur l'intervalle demandé...",
        "Extraction WAV standardisée...",
        "Transcription Whisper...",
        "Export des segments horodatés..."
      ],
    });
    if (!audioResponse) {
      return;
    }
  }

  const baseOutputDir = getMultimodalBaseOutputDir() || "multimodale/exports";
  setReadonlyStatus(multimodalYtdlpRunStatus, `Terminé. Exports écrits dans : ${baseOutputDir}`);
  multimodalProgression.set(100, "Export multimodal terminé.");
  setTimeout(() => multimodalProgression.close(), 700);
});

runMultimodalAudioBtn?.addEventListener("click", async () => {
  const request = buildMultimodalAudioArgs();
  if (!request) {
    log("[error] Sélectionnez une source audio, une vidéo ou une URL YouTube.");
    setReadonlyStatus(multimodalAudioRunStatus, "Sélectionnez une source audio, une vidéo ou une URL YouTube.", { isError: true });
    return;
  }
  await runMultimodalScript(request, {
    title: "Analyse audio",
    message: "Transcription et indicateurs audio en cours...",
    statusElement: multimodalAudioRunStatus,
    actionButton: runMultimodalAudioBtn,
    plannedStages: [
      "Préparation de la source audio...",
      "Découpage sur l'intervalle demandé...",
      "Extraction WAV standardisée...",
      "Transcription Whisper...",
      "Calcul des pauses et indicateurs audio...",
      "Export des tableaux et du graphe Altair..."
    ],
  });
});

runMultimodalMotionBtn?.addEventListener("click", async () => {
  if (multimodalMotionFaceAnalysisMode?.value === "manuel" && !getMultimodalSelectedFaceBoxArg()) {
    const message = "Dessine d'abord un rectangle sur le visage à suivre avec « Sélectionner le visage à la souris ».";
    log(`[error] ${message}`);
    setReadonlyStatus(multimodalMotionRunStatus, message, { isError: true });
    return;
  }
  const request = buildMultimodalMotionArgs();
  if (!request) {
    log("[error] Sélectionnez ou préparez d'abord une séquence d'images pour l'analyse des mouvements.");
    setReadonlyStatus(multimodalMotionRunStatus, "Sélectionnez ou préparez d'abord une séquence d'images pour l'analyse des mouvements.", { isError: true });
    return;
  }
  multimodalProgression.open("Analyse mouvements", "Préparation de la séquence d'images...");
  multimodalProgression.set(1, "Préparation de la séquence d'images...");
  await waitForNextPaintFrame();
  const response = await runMultimodalScript(request, {
    title: "Analyse mouvements",
    message: "Optical flow et indicateurs vidéo en cours...",
    statusElement: multimodalMotionRunStatus,
    actionButton: runMultimodalMotionBtn,
    openProgress: false,
    plannedStages: [
      "Préparation de la séquence d'images...",
      "Calcul de l'optical flow...",
      "Détection de la zone anatomique choisie...",
      "Calcul des indicateurs ROI et sous-zones...",
      "Agrégation des fenêtres temporelles...",
      "Génération des vues magnitude, HSV, vecteurs, superposition et annotée..."
    ],
  });
  if (response) {
    updateMotionRunStatusFromSummary();
  }
});

runMultimodalAlignBtn?.addEventListener("click", async () => {
  const request = buildMultimodalAlignArgs();
  if (!request) {
    log("[error] Sélectionnez des images ou une vidéo, puis un CSV de segments.");
    setReadonlyStatus(multimodalAlignRunStatus, "Sélectionnez des images ou une vidéo, puis un CSV de segments.", { isError: true });
    return;
  }
  await runMultimodalScript(request, {
    title: "Alignement multimodal",
    message: "Alignement des images et des segments en cours...",
    statusElement: multimodalAlignRunStatus,
    actionButton: runMultimodalAlignBtn,
    plannedStages: [
      "Préparation de la source visuelle...",
      "Chargement ou extraction des images...",
      "Chargement du CSV de segments...",
      "Alignement segment ↔ images...",
      "Export du tableau et du graphe Altair..."
    ],
  });
});

runMultimodalNodesBtn?.addEventListener("click", async () => {
  const request = buildMultimodalNodesArgs();
  if (!request) {
    log("[error] Lance d'abord l'alignement et garde les mouvements disponibles pour construire les nœuds.");
    setReadonlyStatus(multimodalNodesRunStatus, "Lance d'abord l'alignement et garde les mouvements disponibles pour construire les nœuds.", { isError: true });
    return;
  }
  await runMultimodalScript(request, {
    title: "Carte réseau",
    message: "Construction des noeuds multimodaux en cours...",
    statusElement: multimodalNodesRunStatus,
    actionButton: runMultimodalNodesBtn,
    plannedStages: [
      "Chargement de l'alignement...",
      "Repérage des pics d'entropie...",
      "Regroupement en événements visuels...",
      "Association aux segments de texte...",
      "Calcul des liens temporels, visuels et lexicaux...",
      "Export du graphe et des tableaux..."
    ],
  });
});

multimodalNodesEventMode?.addEventListener("change", () => {
  syncMultimodalNodesControls();
});

runMultimodalCompareAbBtn?.addEventListener("click", async () => {
  await runMultimodalComparisonAbPipeline();
});

annotationCorpusText?.addEventListener("input", () => {
  renderAnnotationPreview();
});

annotationCorpusText?.addEventListener("mouseup", () => {
  updateAnnotationSelectionFields(getAnnotationSelectionFromTextarea());
});

annotationCorpusText?.addEventListener("keyup", () => {
  updateAnnotationSelectionFields(getAnnotationSelectionFromTextarea());
});

annotationSelection?.addEventListener("input", () => {
  if (annotationNorm) {
    annotationNorm.value = buildAnnotationNormValue(annotationSelection.value);
  }
});

annotationAddEntryBtn?.addEventListener("click", () => {
  try {
    const selectionValue =
      annotationSelection?.value || getAnnotationSelectionFromTextarea() || "";
    const dicMot = normalizeAnnotationSelectionValue(selectionValue);
    const dicNorm =
      normalizeAnnotationSelectionValue(annotationNorm?.value) || buildAnnotationNormValue(selectionValue);
    const dicMorpho = normalizeAnnotationMorphoValue(annotationMorpho?.value);

    if (!dicMot || !dicNorm) {
      log("[error] dic_mot et dic_norm sont obligatoires.");
      return;
    }

    const entries = [...appState.expressionAnnotations];
    const existingIndex = entries.findIndex((entry) => entry.dic_mot === dicMot);
    const entry = { dic_mot: dicMot, dic_norm: dicNorm, dic_morpho: dicMorpho };
    if (existingIndex >= 0) {
      entries[existingIndex] = entry;
    } else {
      entries.push(entry);
    }

    setAnnotationEntries(entries);
    fillAnnotationEditor(entry);
    log(
      existingIndex >= 0
        ? `[info] Entrée dictionnaire mise à jour : ${dicMot}.`
        : `[info] Entrée dictionnaire ajoutée : ${dicMot}.`
    );
  } catch (error) {
    log(`[error] Ajout / modification impossible : ${error?.message || String(error)}`);
  }
});

annotationRemoveEntryBtn?.addEventListener("click", () => {
  const key = normalizeAnnotationSelectionValue(annotationRemoveKey?.value);
  if (!key) return;
  setAnnotationEntries(appState.expressionAnnotations.filter((entry) => entry.dic_mot !== key));
  log("[info] Entrée supprimée (si existante).");
});

annotationImportCsv?.addEventListener("change", async () => {
  const file = annotationImportCsv.files?.[0];
  if (!file) return;

  try {
    const text = await file.text();
    const entries = parseAnnotationCsv(text);
    if (!entries.length) {
      log("[error] CSV annotation invalide ou vide : colonnes attendues dic_mot et dic_norm.");
      return;
    }
    setAnnotationEntries(entries, { imported: true });
  } catch (error) {
    log(`[error] Erreur pendant l'import du dictionnaire : ${error?.message || String(error)}`);
  } finally {
    annotationImportCsv.value = "";
  }
});

annotationDownloadCsvBtn?.addEventListener("click", async () => {
  const content = buildAnnotationCsvContent();
  const tauriInvoke = getTauriInvoke();

  if (!tauriInvoke) {
    const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "add_expression_fr.csv";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    log("[info] Export add_expression_fr.csv préparé.");
    setAnnotationSaveStatus("Le navigateur a préparé le téléchargement de add_expression_fr.csv.");
    return;
  }

  try {
    annotationDownloadCsvBtn.disabled = true;
    annotationDownloadCsvBtn.textContent = "Préparation...";
    setAnnotationSaveStatus("Création de l'export add_expression_fr.csv en cours...");
    const payload = await tauriInvoke("save_annotation_dictionary_export", {
      content,
      filename: "add_expression_fr.csv"
    });
    log(`[info] add_expression_fr.csv enregistré : ${payload.savedPath || payload.filename}`);
    setAnnotationSaveStatus(`Fichier enregistré : ${payload.savedPath || payload.filename}`);
    await revealInFileManager(payload.savedPath || payload.filename);
    log("[info] Emplacement de add_expression_fr.csv ouvert dans le gestionnaire de fichiers.");
  } catch (nativeError) {
    try {
      const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "add_expression_fr.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      log("[info] Export add_expression_fr.csv préparé.");
      log(`[info] Cause du fallback : ${nativeError?.message || String(nativeError)}`);
      setAnnotationSaveStatus(
        "Le navigateur a préparé le téléchargement de add_expression_fr.csv. Vérifie ton dossier Téléchargements."
      );
    } catch (fallbackError) {
      log(`[error] Téléchargement de add_expression_fr.csv impossible : ${fallbackError?.message || String(fallbackError)}`);
      setAnnotationSaveStatus(
        `Enregistrement impossible : ${fallbackError?.message || String(fallbackError)}`,
        { isError: true }
      );
    }
  } finally {
    annotationDownloadCsvBtn.disabled = false;
    annotationDownloadCsvBtn.textContent = "Enregistrer add_expression_fr.csv";
  }
});

corpusFileInput.addEventListener("change", async () => {
  const selectedFile = corpusFileInput.files?.[0];

  if (!selectedFile) {
    appState.corpusFileName = null;
    appState.corpusText = "";
    appState.afcStarredVariablesChoices = [];
    appState.corpusStarredDocs = [];
    appState.corpusStarredModalitiesByVariable = {};
    resetSimiTermsState();
    fileInfo.textContent = "Aucun fichier sélectionné.";
    setSidebarRuntimeStatus("");
    corpusPreview.textContent = "Importez un fichier texte pour afficher un extrait ici.";
    if (annotationCorpusText) annotationCorpusText.value = "";
    renderAnnotationPreview();
    renderAfcStarredVariablesPickers(document, { resetSelection: true });
    renderSuiviControls(document, { resetSelection: true });
    renderSimiTermsPickers(document);
    updateDownloadResultsState();
    return;
  }

  resetResultPanes();
  appState.corpusFileName = selectedFile.name;
  fileInfo.textContent = `Fichier: ${selectedFile.name} (${getFileSizeLabel(selectedFile)})`;
  setSidebarRuntimeStatus("");
  await loadCorpusPreview(selectedFile);
  if (annotationCorpusText) {
    annotationCorpusText.value = appState.corpusText;
  }
  renderAnnotationPreview();
  resetSimiTermsState();
  renderSimiTermsPickers(document);
  log(`[info] Corpus sélectionné : ${selectedFile.name}`);
});

document.addEventListener("click", (event) => {
  if (chdTermContextMenu && !chdTermContextMenu.hidden) {
    const target = event.target;
    if (!(target instanceof Node) || !chdTermContextMenu.contains(target)) {
      closeChdTermContextMenu();
    }
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (isMultimodalComparisonAbFullscreen()) {
      setMultimodalComparisonAbFullscreen(false);
      renderMultimodalComparisonAbResults();
    }
    closeChdTermContextMenu();
  }
});

document.addEventListener("scroll", () => {
  closeChdTermContextMenu();
}, true);

document.addEventListener("click", (event) => {
  const anchor = event.target instanceof Element ? event.target.closest("a[href]") : null;
  if (!anchor) return;

  const href = anchor.getAttribute("href");
  if (!href || !/^https?:\/\//i.test(href)) return;

  event.preventDefault();
  void openExternalUrl(href);
});

async function startAnalysis(analysisKind = "chd") {
  const waitForNextPaint = () =>
    new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(resolve));
    });
  const wait = (ms) =>
    new Promise((resolve) => {
      setTimeout(resolve, ms);
    });

  closeParameterDialogs([chdConfigDialog, simiConfigDialog, ldaConfigDialog, suiviConfigDialog, multimodalCompareAbConfigDialog]);

  const selectedFile = corpusFileInput.files?.[0] || null;
  const corpusName = String(appState.corpusFileName || selectedFile?.name || "").trim();

  if (!corpusName || !String(appState.corpusText || "").trim()) {
    activateTopTab("corpus");
    log("[error] Veuillez importer un corpus avant de lancer l'analyse.");
    return;
  }

  const analysis = document.getElementById("analysisType").value;
  const minFreq = Number(document.getElementById("minFreq").value);
  const statsMode = document.getElementById("statsMode").value;
  const kIramuteq = Number(document.getElementById("kIramuteq").value);
  const ldaK = Math.max(2, Number(document.getElementById("ldaK").value) || 6);
  const tauriInvoke = getTauriInvoke();
  const isLdaMode = analysisKind === "lda";
  const isSimiMode = analysisKind === "simi";
  const isSuiviMode = analysisKind === "suivi";

  if (isSuiviMode) {
    log("[error] Le module de trajectoire longitudinale a été retiré de cette version d'IRaMuTeQ Lite.");
    return;
  }

  const navigationTarget = getNavigationTargetForAnalysisKind({ isLdaMode, isSimiMode, isSuiviMode });
  const suiviSelectedUnits = isSuiviMode ? getSelectedMultiSelectValues(suiviInterviewsSelect) : [];
  const suiviAvailableUnits = isSuiviMode ? getSuiviAvailableUnits(document) : [];
  const suiviVariableName = isSuiviMode ? resolveSuiviVariableName(document) : "";
  const suiviFilterVariableName = isSuiviMode
    ? normalizeStarredVariableName(suiviFilterVariable?.value || "")
    : "";
  const suiviFilterModality = isSuiviMode
    ? String(suiviFilterModalite?.value || "").trim()
    : "";
  const suiviAnalysisLayer = isSuiviMode
    ? String(document.getElementById("suiviAnalysisLayer")?.value || "lexicale_brute").trim() || "lexicale_brute"
    : "lexicale_brute";
  const suiviEmotionLexicon = isSuiviMode
    ? String(document.getElementById("suiviEmotionLexicon")?.value || "feel").trim() || "feel"
    : "feel";
  const suiviLexicalUnit = isSuiviMode
    ? String(document.getElementById("suiviLexicalUnit")?.value || "unigramme").trim() || "unigramme"
    : "unigramme";
  const suiviLexicalUnitLabel = suiviLexicalUnit === "bigramme" ? "bigrammes" : "grammes / unigrammes";
  const suiviPreprocessingLabel = document.getElementById("useLemmas").checked ? "lemmes" : "formes";

  if (isSimiMode && !appState.simiTermsChoices.length) {
    activateTopTab("similitudes");
    log("[error] L'analyse de similitudes nécessite d'abord une CHD pour récupérer les termes les plus fréquents.");
    return;
  }

  if (isSuiviMode && suiviAvailableUnits.length < 2) {
    activateTopTab("suivi_longitudinal");
    log("[error] La trajectoire lexicale nécessite au moins deux entretiens ordonnables dans la variable sélectionnée.");
    return;
  }

  if (isSuiviMode && suiviSelectedUnits.length < 2) {
    activateTopTab("suivi_longitudinal");
    log("[error] Sélectionnez au moins deux entretiens pour calculer la trajectoire lexicale.");
    return;
  }

  const progressTitle = isLdaMode
    ? "Analyse LDA"
    : isSimiMode
      ? "Analyse de similitudes"
      : isSuiviMode
        ? "Trajectoire lexicale"
        : "Analyse CHD";
  const progressStartMessage = isLdaMode
    ? "Préparation du modèle LDA..."
    : isSimiMode
      ? "Préparation du graphe de similitudes..."
      : isSuiviMode
        ? "Préparation de la trajectoire lexicale..."
        : "Préparation de la CHD...";

  setSidebarRuntimeStatus("Verification de l'acces serveur...");
  activateTopTab("analyse");
  progression.open(progressTitle, progressStartMessage);
  await waitForNextPaint();
  if (isLdaMode) {
    log(`[info] Démarrage analyse LDA : topics=${ldaK}, unité=${document.getElementById("language").value}`);
  } else if (isSimiMode) {
    log(`[info] Démarrage analyse de similitudes : méthode=${document.getElementById("simiMethod").value}`);
  } else if (isSuiviMode) {
    const coucheLabel = suiviAnalysisLayer === "emotionnelle"
      ? `couche=émotionnelle (${suiviEmotionLexicon.toUpperCase()})`
      : "couche=lexicale brute";
    log(
      `[info] Démarrage trajectoire lexicale : variable=${suiviVariableName || "auto"}, entretiens=${suiviSelectedUnits.length}, ${coucheLabel}, unité=${suiviLexicalUnitLabel}, prétraitement=${suiviPreprocessingLabel}${suiviFilterVariableName && suiviFilterModality ? `, filtre=${suiviFilterVariableName}=${suiviFilterModality}` : ""}`
    );
  } else {
    log(
      `[info] Démarrage analyse : moteur=${analysis}, classes=${kIramuteq}, minFreq=${minFreq}, stats=${statsMode}`
    );
  }
  progression.set(4, progressStartMessage);

  if (!tauriInvoke) {
    const checkpoints = isLdaMode
      ? [
          [18, "Préparation du corpus"],
          [42, "Segmentation et préparation LDA"],
          [76, "Modélisation des topics"],
          [100, "Exports LDA prêts à afficher"]
        ]
      : isSimiMode
        ? [
            [18, "Préparation du corpus"],
            [46, "Construction de la matrice de similitudes"],
            [82, "Génération du graphe"],
            [100, "Exports similitudes prêts à afficher"]
          ]
      : isSuiviMode
        ? [
            [18, "Préparation des entretiens"],
            [44, "Construction du vocabulaire commun"],
            [72, "Calcul des distributions lexicales"],
            [100, "Exports du suivi prêts à afficher"]
          ]
      : [
          [18, "Préparation du corpus"],
          [36, "Nettoyage et dictionnaire"],
          [61, "Classification CHD"],
          [82, "Exports + tableaux"],
          [100, "Analyse prête à afficher"]
        ];

    for (const [value, message] of checkpoints) {
      await new Promise((resolve) => setTimeout(resolve, 280));
      progression.set(value, message);
      log(`[info] ${message}`);
    }

    renderAnalysisSteps(checkpoints.map(([, message]) => message));
    renderAnalysisSummary(null);
    renderZipfChart(null);
    await refreshTicketSidebarStatus();
    log("[info] Le pipeline R n'est pas disponible hors environnement Tauri.");
    progression.close();
    return;
  }

  let analysisTicket = null;
  try {
    const bootstrap = await ensureDependenciesReady();
    if (!bootstrap?.success) {
      setSidebarRuntimeStatus("Packages incomplets", "error");
      progression.set(0);
      log("[error] L'analyse est bloquée tant que les packages requis ne sont pas installés.");
      progression.close();
      return;
    }

    const corpusText = String(appState.corpusText || "").trim()
      ? appState.corpusText
      : await selectedFile.text();
    const config = buildJobConfig(analysisKind);
    let streamedLogCount = 0;
    let lastTicketHeartbeatAt = 0;

    analysisTicket = await waitForAnalysisTicket(progression, log);
    analysisExecutionInProgress = true;
    updateReleaseAccessButton();
    setSidebarRuntimeStatus("Analyse en cours. L'acces reste reserve pour cette session.");

    progression.set(12, "Envoi du corpus au backend...");
    log("[info] Envoi du corpus à Python pour orchestration du job R.");

    const session = await tauriInvoke("start_python_analysis", {
      corpusName,
      corpusText,
      config
    });
    log(`[info] Job lancé : ${session.jobId}`);

    let payload = null;
    while (!payload) {
      const snapshot = await tauriInvoke("read_python_analysis_status", {
        jobId: session.jobId
      });

      const progressValue = Math.max(4, Math.min(99, Number(snapshot.progress) || 0));
      progression.set(
        snapshot.completed && snapshot.success ? 99 : progressValue,
        snapshot.message || "Traitement du job..."
      );

      const statusLogs = Array.isArray(snapshot.logs) ? snapshot.logs : [];
      if (statusLogs.length > streamedLogCount) {
        statusLogs.slice(streamedLogCount).forEach((line) => log(line));
        streamedLogCount = statusLogs.length;
      }

      if (snapshot.completed) {
        if (!snapshot.success) {
          const failureLines = statusLogs.length ? statusLogs : [snapshot.message || "Le job Python a échoué."];
          throw new Error(failureLines.join("\n"));
        }
        payload = snapshot;
        break;
      }

      if (analysisTicket?.enabled) {
        const now = Date.now();
        if (!lastTicketHeartbeatAt || now - lastTicketHeartbeatAt >= analysisTicket.heartbeatMs) {
          analysisTicket = await heartbeatAnalysisTicket();
          lastTicketHeartbeatAt = now;
          if (analysisTicket?.enabled && analysisTicket.statut !== "actif") {
            throw new Error(analysisTicket.message || "Le ticket actif a ete perdu pendant l'analyse.");
          }
        }
      }

      await wait(350);
    }

    appState.outputDir = payload.outputDir || null;

    progression.set(96, "Traitement des exports...");

    renderAnalysisSteps(payload.logs || []);
    renderAnalysisSummary(payload.summary || null);
    renderZipfChart(payload.summary || null);

    let artifactFiles = [];
    if (payload.outputDir) {
      try {
        const refreshedArtifacts = await tauriInvoke("collect_output_artifacts", {
          outputDir: payload.outputDir
        });
        artifactFiles = Array.isArray(refreshedArtifacts.files) ? refreshedArtifacts.files : [];
      } catch (refreshError) {
        log(
          `[error] Relecture directe des exports impossible : ${refreshError?.message || String(refreshError)}`
        );
      }
    }
    if (!artifactFiles.length && Array.isArray(payload.files)) {
      artifactFiles = payload.files;
    }

    log(`[info] Exports récupérés par l'UI : ${artifactFiles.length} fichier(s).`);

    const virtualFiles = artifactFiles.map((artifact) =>
      createVirtualFileFromArtifact(artifact, payload.jobId || "exports")
    );

    if (virtualFiles.length) {
      await handleExportsFolderSelection(virtualFiles, navigationTarget);
      rememberAnalysisHistoryEntry({
        id: payload.jobId || `${analysisKind}-${Date.now()}`,
        jobId: payload.jobId || null,
        analysisKind,
        createdAt: new Date().toISOString(),
        corpusName,
        folderName: payload.jobId || "exports",
        outputDir: payload.outputDir || null,
        navigationTarget,
        summary: payload.summary || null,
        logs: Array.isArray(payload.logs) ? payload.logs : [],
        artifacts: artifactFiles
      });
    } else {
      log("[error] Aucun export exploitable n'a été récupéré après l'analyse.");
      renderAnalysisDiagnostic(
        [
          "Aucun export exploitable n'a ete recupere apres l'analyse.",
          payload.outputDir ? `Dossier d'exports : ${payload.outputDir}` : "",
          payload.stdoutLog ? `Stdout : ${payload.stdoutLog}` : "",
          payload.stderrLog ? `Stderr : ${payload.stderrLog}` : ""
        ].filter(Boolean).join("\n"),
        navigationTarget
      );
      activateTopTab(navigationTarget);
    }

    progression.set(100, "Analyse terminée.");
    setSidebarTicketStatus("Application active sur cette session", "active");
    setSidebarRuntimeStatus("Analyse terminee. Vous pouvez liberer l'acces ou lancer une nouvelle analyse.", "success");
    const summary = payload.summary || {};
    log(
      isLdaMode
        ? `[info] Analyse LDA terminée : topics=${ldaK}, fichiers=${virtualFiles.length}.`
        : isSimiMode
        ? `[info] Analyse de similitudes terminée : fichiers=${virtualFiles.length}.`
        : isSuiviMode
          ? `[info] Trajectoire lexicale terminée : entretiens=${suiviSelectedUnits.length}, fichiers=${virtualFiles.length}.`
          : `[info] Analyse terminée : segments=${summary.n_segments ?? "?"}, classes=${summary.n_classes ?? "?"}, fichiers=${virtualFiles.length}.`
    );
    log(`[info] Exports backend: ${payload.outputDir}`);
    progression.close();
  } catch (error) {
    setSidebarRuntimeStatus("Echec de l'analyse", "error");
    progression.set(0, "Échec de l'analyse.");
    const message = error?.message || String(error);
    const lines = String(message)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) {
      log("[error] Échec d'analyse sans message détaillé.");
    } else {
      lines.forEach((line, index) => {
        log(index === 0 ? `[error] ${line}` : line);
      });
    }
    renderAnalysisDiagnostic(lines.join("\n"), navigationTarget);
    progression.close();
  } finally {
    analysisExecutionInProgress = false;
    updateReleaseAccessButton();
    scheduleIdleTicketRelease();
    await refreshTicketSidebarStatus();
  }
}

activateTopTab("analyse");
activateChdSubTab("dendrogramme");
activateHelpSubTab("help_general");
resetResultPanes();
renderResults([]);
syncDendrogramSizing();
renderMorphoPickers(document);
renderAfcStarredVariablesPickers(document, { resetSelection: true });
renderLdaMorphoPickers(document);
renderClassificationModeCards(document);
renderSimiTermsPickers(document);
populateAnnotationMorphoOptions();
renderAnnotationDictionaryTable();
renderAnnotationPreview();
void resetAnnotationEntriesOnStartup();
void loadHelpMarkdown(helpMarkdownContent, "help.md");
void loadHelpMarkdown(helpMorphoMarkdownContent, "pos_lexique.md");
void loadHelpMarkdown(helpLdaMarkdownContent, "lda.md");
void claimPageTicketOnOpen().then(() => {
  window.setTimeout(() => {
    void refreshTicketSidebarStatus();
  }, 800);
});
window.setInterval(() => {
  void refreshTicketSidebarStatus();
}, 15000);
if (releaseAccessBtn) {
  releaseAccessBtn.addEventListener("click", async () => {
    releaseAccessBtn.disabled = true;
    try {
      const snapshot = await releaseAnalysisTicket();
      if (snapshot) {
        setSidebarRuntimeStatus("Acces libere pour cette session.", "success");
      } else {
        setSidebarRuntimeStatus("Liberation a reessayer : le statut va etre reverifie.", "error");
      }
    } finally {
      await refreshTicketSidebarStatus();
      updateReleaseAccessButton();
    }
  });
}
window.addEventListener("pointerdown", rememberUserInteraction, { passive: true });
window.addEventListener("keydown", rememberUserInteraction);
window.addEventListener("scroll", rememberUserInteraction, { passive: true });
window.addEventListener("pagehide", releaseTicketOnPageHide);
window.addEventListener("beforeunload", releaseTicketOnPageHide);

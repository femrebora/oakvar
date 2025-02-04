var gridObjs = {}
var $grids = {}
var columnGroupPrefix = 'columngroup_';
var selectedRowIds = {};
var selectedRowNos = {};
var username = null;
var jobId = null;
var currentTab = null;
var ascendingSort = {};
var resultLevels = null;
var onemut = null;
var infomgr = new InfoMgr();
var jobDataLoadingDiv = null;
var widgetInfo = null;
var detailWidgetOrder = {};
var dbPath = null;
var filterJson = {};
var filterCols = null;
var filterArmed = {};
var resetTab = {};
var spinner = null;
var shouldResizeScreen = {};
var NUMVAR_LIMIT = 100000;
var firstLoad = true;
var confPath = null;
var tableSettings = {};
var loadedTableSettings = {};
var viewerWidgetSettings = {};
var loadedViewerWidgetSettings = {};
var loadedHeightSettings = {};
var quickSaveName = 'quicksave-name-internal-use';
var lastUsedLayoutName = '';
var savedLayoutNames = null;
var autoSaveLayout = true;
var windowWidth = 0;
var windowHeight = 0;
var tableDetailDivSizes = {};
var showcaseWidgets = {'info': ['sosamplesummary', 'ndexchasmplussummary', 'ndexvestsummary', 'sosummary', 'gosummary', 'circossummary'], 'variant': ['base'], 'gene': ['base']};
var geneRows = {};
var colgroupkeysWithMissingCols = [];
var separateSample = false;
var allSamples = [];
var smartFilters = {};
var showFilterTabContent = false;
var lastUsedFilterName = null;
var pageNo = 1;
//var pageSize = 100000
var variantdbcols = null
const tabNames = ["job", "filter", "info", "variant", "gene", "report"]
var masons = {}
const defaultDetailDivWidth = 620
var widgetWidthGridSize = 600;
var widgetHeightGridSize = 300;
var tableHightlighBackgroundColor = "rgb(188, 218, 251)"

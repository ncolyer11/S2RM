package com.github.winplay02.gitcraft;

import com.github.winplay02.gitcraft.config.ApplicationConfiguration;
import com.github.winplay02.gitcraft.config.Configuration;
import com.github.winplay02.gitcraft.config.DataConfiguration;
import com.github.winplay02.gitcraft.config.GlobalConfiguration;
import com.github.winplay02.gitcraft.config.IntegrityConfiguration;
import com.github.winplay02.gitcraft.config.RepositoryConfiguration;
import com.github.winplay02.gitcraft.config.TransientApplicationConfiguration;
import com.github.winplay02.gitcraft.exceptions.ExceptionsFlavour;
import com.github.winplay02.gitcraft.manifest.metadata.VersionInfo;
import com.github.winplay02.gitcraft.mappings.MappingFlavour;
import com.github.winplay02.gitcraft.nests.NestsFlavour;
import com.github.winplay02.gitcraft.pipeline.GitCraftPipelineDescription;
import com.github.winplay02.gitcraft.pipeline.GitCraftPipelineFilesystemStorage;
import com.github.winplay02.gitcraft.pipeline.GitCraftStepConfig;
import com.github.winplay02.gitcraft.pipeline.IPipeline;
import com.github.winplay02.gitcraft.pipeline.IStepContext;
import com.github.winplay02.gitcraft.pipeline.PipelineFilesystemStorage;
import com.github.winplay02.gitcraft.signatures.SignaturesFlavour;
import com.github.winplay02.gitcraft.types.OrderedVersion;
import com.github.winplay02.gitcraft.unpick.UnpickFlavour;
import com.github.winplay02.gitcraft.util.MiscHelper;
import com.github.winplay02.gitcraft.util.SerializationHelper;
import com.github.winplay02.gitcraft.util.SerializationTypes;
import net.fabricmc.loom.util.FileSystemUtil;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Minimal entry point that fetches, remaps, and decompiles a single Minecraft version, then copies
 * only the requested sources into {@code game_data/<version>/minecraft/src}.
 */
public final class SimpleSourceExtractor extends GitCraftApplication {
	private static final List<String> TARGET_SOURCES = List.of(
		"net/minecraft/world/item/Items.java",
		"net/minecraft/world/level/block/Blocks.java",
		"net/minecraft/world/entity/EntityType.java"
	);

	private static final Pattern VERSION_TOKEN_PATTERN = Pattern.compile("([0-9]+(?:[._-][0-9A-Za-z]+)*)");

	private final String targetVersion;
	private final Path outputRoot;

	private SimpleSourceExtractor(String targetVersion, Path outputRoot) {
		this.targetVersion = Objects.requireNonNull(targetVersion, "version");
		this.outputRoot = Objects.requireNonNull(outputRoot, "output root").toAbsolutePath().normalize();
	}

	public static List<Path> extract(String version) throws Exception {
		return extract(version, Paths.get("game_data"));
	}

	public static List<Path> extract(String version, Path outputRoot) throws Exception {
		String normalizedVersion = normalizeVersionInput(Objects.requireNonNull(version, "version"));
		if (!isSupportedVersion(normalizedVersion)) {
			throw new IllegalArgumentException("Only Minecraft 1.21.0 or newer releases are supported");
		}
		SimpleSourceExtractor extractor = new SimpleSourceExtractor(normalizedVersion, outputRoot);
		extractor.mainEntrypoint(new String[0]);
		return extractor.lastExtracted;
	}

	public static void main(String[] args) throws Exception {
		String rawVersion = null;
		Path output = Paths.get("game_data");
		for (int i = 0; i < args.length; i++) {
			String arg = args[i];
			if ("-o".equals(arg) || "--output".equals(arg)) {
				if (i + 1 >= args.length) {
					System.err.println("Missing path after " + arg);
					System.exit(1);
				}
				output = Paths.get(args[++i]);
				continue;
			}
			if (arg.startsWith("--output=")) {
				output = Paths.get(arg.substring("--output=".length()));
				continue;
			}
			rawVersion = rawVersion == null ? arg : rawVersion + " " + arg;
		}
		if (rawVersion == null) {
			rawVersion = promptForVersion();
		}
		extract(rawVersion, output);
	}

	@Override
	public boolean initialize(String... args) {
		Configuration.reset();
		Configuration.register("global", GlobalConfiguration.class, GlobalConfiguration::deserialize);
		Configuration.register("integrity", IntegrityConfiguration.class, IntegrityConfiguration::deserialize);
		Configuration.register("gitcraft_repository", RepositoryConfiguration.class, RepositoryConfiguration::deserialize);
		Configuration.register("gitcraft_dataimport", DataConfiguration.class, DataConfiguration::deserialize);
		Configuration.register("gitcraft_application", ApplicationConfiguration.class, ApplicationConfiguration::deserialize);
		Configuration.register("gitcraft_application_transient", TransientApplicationConfiguration.class, TransientApplicationConfiguration::deserialize);
		SerializationHelper.registerTypeAdapter(VersionInfo.VersionArgumentWithRules.class, SerializationTypes.VersionArgumentWithRulesAdapter::new);

		Configuration.editConfiguration(GlobalConfiguration.class, original -> new GlobalConfiguration(
			original.checksumRemoveInvalidFiles(),
			original.printExistingFileChecksumMatching(),
			original.printExistingFileChecksumMatchingSkipped(),
			original.printNotRunSteps(),
			original.failedFetchRetryInterval(),
			Math.max(1, Math.min(2, original.remappingThreads())),
			Math.max(1, Math.min(2, original.decompilingThreads())),
			original.useHardlinks(),
			original.maxConcurrentHttpStreams(),
			original.maxConcurrentHttpConnections(),
			Math.min(16, original.maxConcurrentHttpRequestsPerOrigin()),
			1
		));

		Configuration.editConfiguration(IntegrityConfiguration.class, original -> new IntegrityConfiguration(false, false));
		Configuration.editConfiguration(DataConfiguration.class, original -> new DataConfiguration(false, false, false, false, false, false));
		Configuration.editConfiguration(ApplicationConfiguration.class, original -> new ApplicationConfiguration(
			original.manifestSource(),
			MappingFlavour.MOJMAP,
			new MappingFlavour[0],
			UnpickFlavour.NONE,
			new UnpickFlavour[0],
			false,
			false,
			false,
			false,
			new String[]{this.targetVersion},
			null,
			null,
			null,
			original.ornitheIntermediaryGeneration(),
			false,
			ExceptionsFlavour.NONE,
			SignaturesFlavour.NONE,
			NestsFlavour.NONE,
			false
		));
		Configuration.editConfiguration(TransientApplicationConfiguration.class, original -> new TransientApplicationConfiguration(true, null, false, null, null, null));
		return true;
	}

	@Override
	public void run() throws Exception {
		MiscHelper.println("Preparing sources for %s", this.targetVersion);
		try {
			versionGraph = doVersionGraphOperations(versionGraph);
			OrderedVersion version = versionGraph.getMinecraftVersionByName(this.targetVersion);
			if (version == null) {
				MiscHelper.panic("Unknown Minecraft version: %s", this.targetVersion);
			}

			IPipeline.run(GitCraftPipelineDescription.DEFAULT_PIPELINE, GitCraftPipelineFilesystemStorage.DEFAULT.get(), null, versionGraph);
			extractSelectedSources(version);
		} finally {
			cleanupTemporaryArtifacts();
		}
	}

	private void extractSelectedSources(OrderedVersion version) throws IOException {
		GitCraftStepConfig config = GitCraftPipelineDescription.getConfig(version);
		IStepContext.SimpleStepContext<OrderedVersion> context = new IStepContext.SimpleStepContext<>(null, versionGraph, version, null);
		PipelineFilesystemStorage<OrderedVersion, IStepContext.SimpleStepContext<OrderedVersion>, GitCraftStepConfig> storage = GitCraftPipelineFilesystemStorage.DEFAULT.get();

		Path mergedJar = storage.getPath(GitCraftPipelineFilesystemStorage.DECOMPILED_MERGED_JAR, context, config);
		Path clientJar = storage.getPath(GitCraftPipelineFilesystemStorage.DECOMPILED_CLIENT_JAR, context, config);
		Path serverJar = storage.getPath(GitCraftPipelineFilesystemStorage.DECOMPILED_SERVER_JAR, context, config);

		Path versionOutput = this.outputRoot.resolve(sanitizedVersionSegment(version.launcherFriendlyVersionName()));
		Files.createDirectories(versionOutput);
		this.lastExtracted = TARGET_SOURCES.stream()
			.map(SimpleSourceExtractor::extractFileName)
			.map(versionOutput::resolve)
			.toList();

		for (int i = 0; i < TARGET_SOURCES.size(); i++) {
			String source = TARGET_SOURCES.get(i);
			Path destination = this.lastExtracted.get(i);
			boolean extracted = tryCopyFromJar(mergedJar, source, destination);
			if (!extracted) {
				extracted = tryCopyFromJar(clientJar, source, destination);
			}
			if (!extracted) {
				extracted = tryCopyFromJar(serverJar, source, destination);
			}
			if (!extracted) {
				throw new IOException("Could not locate " + source + " in any decompiled jar for version " + version.launcherFriendlyVersionName());
			}
		}
		MiscHelper.println("Selected sources copied to %s", versionOutput);
	}

	private static Path extractFileName(String sourcePath) {
		int idx = sourcePath.lastIndexOf('/');
		String fileName = idx >= 0 ? sourcePath.substring(idx + 1) : sourcePath;
		return Path.of(fileName);
	}

	private List<Path> lastExtracted = List.of();

	private void cleanupTemporaryArtifacts() {
		cleanupPathQuietly(LibraryPaths.MAIN_ARTIFACT_STORE);
		cleanupPathQuietly(LibraryPaths.TMP_DIR);
	}

	private void cleanupPathQuietly(Path path) {
		if (path == null) {
			return;
		}
		if (!path.startsWith(LibraryPaths.CURRENT_WORKING_DIRECTORY)) {
			return;
		}
		try {
			MiscHelper.deleteDirectory(path);
		} catch (IOException e) {
			MiscHelper.println("WARNING: Could not remove temporary directory %s (%s)", path, e.getMessage());
		}
	}

	private static boolean tryCopyFromJar(Path jar, String source, Path destination) throws IOException {
		if (jar == null || !Files.exists(jar)) {
			return false;
		}
		try (FileSystemUtil.Delegate fs = FileSystemUtil.getJarFileSystem(jar)) {
			Path inside = fs.get().getPath(source);
			if (!Files.exists(inside)) {
				return false;
			}
			Files.copy(inside, destination, StandardCopyOption.REPLACE_EXISTING);
			return true;
		}
	}

	private static String sanitizedVersionSegment(String version) {
		StringBuilder builder = new StringBuilder(version.length());
		for (int i = 0; i < version.length(); i++) {
			char c = version.charAt(i);
			if (Character.isLetterOrDigit(c) || c == '.' || c == '-' || c == '_') {
				builder.append(c);
			} else {
				builder.append('_');
			}
		}
		return builder.toString();
	}

	private static boolean isSupportedVersion(String version) {
		String numeric = version.split("-", 2)[0];
		String[] parts = numeric.split("\\.");
		int[] numbers = new int[3];
		for (int i = 0; i < Math.min(parts.length, 3); i++) {
			numbers[i] = parseIntSafely(parts[i]);
		}
		int major = numbers[0];
		int minor = numbers[1];
		int patch = numbers[2];
		if (major > 1) {
			return true;
		}
		if (major < 1) {
			return false;
		}
		if (minor > 21) {
			return true;
		}
		if (minor < 21) {
			return false;
		}
		return patch >= 0;
	}

	private static int parseIntSafely(String part) {
		StringBuilder digits = new StringBuilder(part.length());
		for (int i = 0; i < part.length(); i++) {
			char c = part.charAt(i);
			if (Character.isDigit(c)) {
				digits.append(c);
			} else {
				break;
			}
		}
		if (digits.isEmpty()) {
			return 0;
		}
		return Integer.parseInt(digits.toString());
	}

	private static String normalizeVersionInput(String rawInput) {
		String candidate = rawInput.trim();
		Matcher matcher = VERSION_TOKEN_PATTERN.matcher(candidate);
		if (!matcher.find()) {
			throw new IllegalArgumentException("Could not parse a Minecraft version from input: " + rawInput);
		}
		String token = matcher.group(1);
		return token.replace('_', '.');
	}

	private static String promptForVersion() throws IOException {
		System.out.print("Enter Minecraft version: ");
		System.out.flush();
		BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
		String line = reader.readLine();
		if (line == null || line.isBlank()) {
			throw new IllegalArgumentException("No version provided; aborting extractor.");
		}
		return line;
	}
}

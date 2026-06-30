package com.pixelos.office.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

data class Slide(val id: String, val title: String, val bgColor: Long)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SlidesScreen(onBack: () -> Unit) {
    var slides by remember {
        mutableStateOf(listOf(
            Slide("s1", "Rapport Récolte 2026", 0xFFE8F5E9),
            Slide("s2", "Évolution des rendements", 0xFFE3F2FD),
            Slide("s3", "Objectifs Q3", 0xFFFFF3E0)
        ))
    }
    var currentSlide by remember { mutableStateOf(0) }
    var editTitle by remember { mutableStateOf(slides.first().title) }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("PixSlides") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } },
                actions = { IconButton({ /* ajouter slide */ }) { Icon(Icons.Default.Add, null) } })
        }
    ) { padding ->
        Row(Modifier.fillMaxSize().padding(padding)) {
            LazyColumn(Modifier.width(120.dp)) {
                items(slides) { slide ->
                    Card(Modifier.padding(4.dp).height(80.dp), colors = CardDefaults.cardColors(containerColor = androidx.compose.ui.graphics.Color(slide.bgColor))) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(slide.title, style = MaterialTheme.typography.labelSmall) }
                    }
                }
            }
            Column(Modifier.weight(1f).padding(16.dp)) {
                Card(Modifier.fillMaxWidth().height(300.dp), colors = CardDefaults.cardColors(containerColor = androidx.compose.ui.graphics.Color(slides[currentSlide].bgColor))) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(slides[currentSlide].title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(8.dp))
                            Text("Sous-titre et contenu", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = editTitle, onValueChange = { editTitle = it; slides = slides.toMutableList().also { it[currentSlide] = it[currentSlide].copy(title = editTitle) } }, label = { Text("Titre") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton({ if (currentSlide > 0) { currentSlide--; editTitle = slides[currentSlide].title } }) { Icon(Icons.Default.NavigateBefore, null, Modifier.padding(end = 4.dp)); Text("Précédent") }
                    Button({ if (currentSlide < slides.size - 1) { currentSlide++; editTitle = slides[currentSlide].title } }) { Text("Suivant"); Icon(Icons.Default.NavigateNext, null, Modifier.padding(start = 4.dp)) }
                }
            }
        }
    }
}

fetch("/static/diseaseprediction/js/symptom.json")
    .then(response => response.json()) // Convert response to JSON directly
    .then(jsonData => {
        // console.log("JSON Data Type:", typeof jsonData); // Check the data type
        // console.log("JSON Data:", jsonData["columns"]); // ✅ Debugging Output
        addtoSelect(jsonData["column"]); // ✅ Pass the JSON data to the function
    })
    .catch(error => console.error("Error loading JSON:", error));

const addtoSelect = (jsonData) => {
    // console.log("Inside addtoSelect:", jsonData);
    // Example: Using the data to add options to a select dropdown
    let select = document.getElementById("optionSelect"); // Ensure you have a select element in HTML
    // console.log(select)

    jsonData.forEach(symptom => {
        let option = document.createElement("option");
        option.value = symptom;
        option.textContent = symptom;
        select.appendChild(option);
    });
};



let selectedSymptoms = []; // Array to store selected symptoms

function addOption() {
    let select = document.getElementById("optionSelect");
    let selectedValue = select.value;
                
    // Check if the option is already added
    if (document.getElementById("opt-" + selectedValue)) {
        alert("Option already added!");
        return;
    }
    
    let selectedDiv = document.getElementById("selectedOptions");
    
    // Create a new div to display selected option
    let div = document.createElement("div");
    div.className = "option-item flex items-center justify-between p-1 mb-1 border bg-gradient-to-br from-blue-100 to-purple-100 rounded-md overflow-y-auto";
    div.id = "opt-" + selectedValue;
    div.innerHTML = `
        ${selectedValue} 
        <button class="remove-btn ml-2 text-sm text-red-500 hover:text-red-700" onclick="removeOption('${selectedValue}')">Remove</button>
    `;

    selectedDiv.appendChild(div);
    
    // Add the symptom to the array
    selectedSymptoms.push(selectedValue);
    updateHiddenInput();
}

function removeOption(value) {
    let div = document.getElementById("opt-" + value);
    if (div) {
        div.remove();
        
        // Remove the symptom from the array
        selectedSymptoms = selectedSymptoms.filter(symptom => symptom !== value);
        updateHiddenInput();
    }
}

// Update the hidden input field with selected symptoms
function updateHiddenInput() {
    document.getElementById("selectedSymptomsInput").value = selectedSymptoms.join(",");
}




